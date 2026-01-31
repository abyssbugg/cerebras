"""
Context Manager Service

Manages conversation context to prevent exceeding Cerebras token limits.
Cerebras zai-glm-4.7 has 128K token limit vs Claude's 200K.

Strategies:
1. Estimate token count from character count (~4 chars = 1 token)
2. If over limit, drop oldest messages (keeping system prompt)
3. Add truncation notice so the model knows context was reduced
"""

from typing import List, Tuple
from app.config import get_settings
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Approximate: 3 characters = 1 token (more conservative for safety)
# Using 3 instead of 4 to account for tokenizer differences
CHARS_PER_TOKEN = 3


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length."""
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN


def estimate_message_tokens(message: dict) -> int:
    """Estimate tokens in a single message."""
    tokens = 0
    
    # Role overhead
    tokens += 4  # role token
    
    # Content
    content = message.get("content", "")
    if isinstance(content, str):
        tokens += estimate_tokens(content)
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    tokens += estimate_tokens(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tokens += estimate_tokens(str(block.get("input", {})))
                elif block.get("type") == "tool_result":
                    result = block.get("content", "")
                    if isinstance(result, str):
                        tokens += estimate_tokens(result)
                    else:
                        tokens += estimate_tokens(str(result))
    
    # Tool calls (for Cerebras format)
    tool_calls = message.get("tool_calls") or []
    for tc in tool_calls:
        if isinstance(tc, dict):
            tokens += estimate_tokens(str(tc.get("function", {}).get("arguments", "")))
    
    return tokens


def estimate_conversation_tokens(messages: List[dict]) -> int:
    """Estimate total tokens in a conversation."""
    return sum(estimate_message_tokens(m) for m in messages)


def truncate_conversation(
    messages: List[dict],
    max_tokens: int = None,
    preserve_system: bool = True
) -> Tuple[List[dict], int, bool]:
    """
    Truncate conversation to fit within token limit.
    
    Strategy:
    - Always preserve system messages
    - Keep the most recent messages
    - Drop oldest user/assistant messages first
    
    Args:
        messages: List of messages (Cerebras format)
        max_tokens: Maximum tokens allowed (default from settings)
        preserve_system: Always keep system messages
    
    Returns:
        Tuple of (truncated_messages, tokens_used, was_truncated)
    """
    if max_tokens is None:
        max_tokens = settings.context_limit_tokens
    
    # Leave room for response (reserve ~4K tokens)
    target_tokens = max_tokens - 4000
    
    current_tokens = estimate_conversation_tokens(messages)
    
    if current_tokens <= target_tokens:
        return messages, current_tokens, False
    
    logger.warning(
        "Conversation exceeds token limit, truncating",
        current_tokens=current_tokens,
        target_tokens=target_tokens
    )
    
    # Separate system messages from conversation
    system_messages = []
    conversation = []
    
    for msg in messages:
        if msg.get("role") == "system":
            system_messages.append(msg)
        else:
            conversation.append(msg)
    
    # Calculate tokens used by system messages (always preserved)
    system_tokens = estimate_conversation_tokens(system_messages)
    available_tokens = target_tokens - system_tokens
    
    # Drop oldest messages until we fit
    # IMPORTANT: Keep tool call/result pairs together to avoid API errors
    truncated_conversation = []
    conversation_tokens = 0
    messages_dropped = 0
    
    # Process from newest to oldest (reverse), then reverse back
    # But we need to handle tool calls and tool results as pairs
    i = len(conversation) - 1
    while i >= 0:
        msg = conversation[i]
        msg_tokens = estimate_message_tokens(msg)
        
        # Check if this is a tool result - if so, we need the preceding assistant message too
        if msg.get("role") == "tool":
            # Find the preceding assistant message with tool_calls
            pair_tokens = msg_tokens
            pair_messages = [msg]
            j = i - 1
            
            # Look backwards for the assistant message with tool_calls
            while j >= 0:
                prev_msg = conversation[j]
                prev_tokens = estimate_message_tokens(prev_msg)
                pair_tokens += prev_tokens
                pair_messages.insert(0, prev_msg)
                
                # Check if this is the assistant message with tool_calls
                if prev_msg.get("role") == "assistant" and prev_msg.get("tool_calls"):
                    break
                j -= 1
            
            # Check if the whole pair fits
            if conversation_tokens + pair_tokens <= available_tokens:
                for m in pair_messages:
                    truncated_conversation.insert(0, m)
                conversation_tokens += pair_tokens
                i = j - 1  # Skip past the messages we just added
            else:
                # Drop the entire pair
                messages_dropped += len(pair_messages)
                i = j - 1
        else:
            # Regular message (user or assistant without tool results following)
            if conversation_tokens + msg_tokens <= available_tokens:
                truncated_conversation.insert(0, msg)
                conversation_tokens += msg_tokens
            else:
                messages_dropped += 1
            i -= 1
    
    # Add truncation notice as first user message if we dropped anything
    if messages_dropped > 0:
        truncation_notice = {
            "role": "system",
            "content": (
                f"[CONTEXT TRUNCATED: {messages_dropped} older messages were removed "
                f"to fit within context limit. The conversation continues from here.]"
            )
        }
        
        # Insert notice after system messages, before conversation
        result = system_messages + [truncation_notice] + truncated_conversation
        
        logger.info(
            "Conversation truncated",
            messages_dropped=messages_dropped,
            original_tokens=current_tokens,
            new_tokens=system_tokens + conversation_tokens + 50  # +50 for notice
        )
    else:
        result = system_messages + truncated_conversation
    
    final_tokens = estimate_conversation_tokens(result)
    return result, final_tokens, messages_dropped > 0


def check_context_limit(messages: List[dict]) -> dict:
    """
    Check if conversation is approaching or exceeding context limit.
    
    Returns status dict with:
    - within_limit: bool
    - estimated_tokens: int
    - max_tokens: int
    - percentage_used: float
    - warning: str or None
    """
    max_tokens = settings.context_limit_tokens
    estimated = estimate_conversation_tokens(messages)
    percentage = (estimated / max_tokens) * 100
    
    result = {
        "within_limit": estimated <= max_tokens,
        "estimated_tokens": estimated,
        "max_tokens": max_tokens,
        "percentage_used": round(percentage, 1)
    }
    
    if percentage > 90:
        result["warning"] = "Context is 90%+ full. Consider starting a new conversation."
    elif percentage > 75:
        result["warning"] = "Context is 75%+ full."
    else:
        result["warning"] = None
    
    return result
