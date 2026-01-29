from typing import List, Optional
from app.models.anthropic import (
    AnthropicMessagesRequest,
    Message,
    TextContent,
    ImageContent,
    ToolUseContent,
    ToolResultContent,
)
from app.models.cerebras import CerebrasMessage, CerebrasChatRequest, CerebrasTool
from app.config import get_settings
from app.utils.logging import get_logger
from app.services.context_manager import truncate_conversation

settings = get_settings()
logger = get_logger(__name__)

MODEL_MAPPING = {
    # All Claude models map to zai-glm-4.7 (Cerebras Code Max)
    "claude-3-5-sonnet-20241022": "zai-glm-4.7",
    "claude-3-5-sonnet-latest": "zai-glm-4.7",
    "claude-sonnet-4-20250514": "zai-glm-4.7",
    "claude-sonnet-4": "zai-glm-4.7",
    "claude-3-5-haiku-20241022": "zai-glm-4.7",
    "claude-3-5-haiku-latest": "zai-glm-4.7",
    "claude-3-opus-20240229": "zai-glm-4.7",
    "claude-3-opus-latest": "zai-glm-4.7",
    "claude-3-haiku-20240307": "zai-glm-4.7",
}


def get_cerebras_model(anthropic_model: str) -> str:
    return MODEL_MAPPING.get(anthropic_model, settings.cerebras_model)


def truncate_content(content: str, max_chars: int, context: str = "content") -> str:
    """
    Truncate content if it exceeds max_chars.
    
    Truncation strategies (configurable via TRUNCATION_STRATEGY):
    - "truncate": Cut content and add truncation notice
    - "error": Raise error if content too long
    - "warn": Log warning but keep full content
    
    Args:
        content: The content to potentially truncate
        max_chars: Maximum characters allowed (0 = no limit)
        context: Description for logging (e.g., "file read", "tool result")
    
    Returns:
        Truncated content with notice, or original content
    """
    if not settings.truncation_enabled or max_chars <= 0:
        return content
    
    if len(content) <= max_chars:
        return content
    
    strategy = settings.truncation_strategy.lower()
    
    if strategy == "error":
        raise ValueError(
            f"Content too long: {len(content)} chars exceeds {max_chars} limit. "
            f"Context: {context}. Set TRUNCATION_STRATEGY=truncate to auto-truncate."
        )
    
    if strategy == "warn":
        logger.warning(
            f"Content exceeds limit but not truncating",
            content_length=len(content),
            max_chars=max_chars,
            context=context
        )
        return content
    
    # Default: truncate
    truncated = content[:max_chars]
    chars_removed = len(content) - max_chars
    
    truncation_notice = (
        f"\n\n[TRUNCATED: Content was {len(content):,} chars, "
        f"showing first {max_chars:,} chars. {chars_removed:,} chars removed to fit context limit.]"
    )
    
    logger.info(
        f"Truncated {context}",
        original_length=len(content),
        truncated_length=max_chars,
        chars_removed=chars_removed
    )
    
    return truncated + truncation_notice


def extract_text_from_content(content) -> str:
    """Extract only text content, ignoring tool_use and tool_result blocks."""
    if isinstance(content, str):
        return content
    
    text_parts = []
    for block in content:
        if isinstance(block, TextContent) or (isinstance(block, dict) and block.get("type") == "text"):
            text = block.text if isinstance(block, TextContent) else block.get("text", "")
            text_parts.append(text)
        elif isinstance(block, ImageContent) or (isinstance(block, dict) and block.get("type") == "image"):
            text_parts.append("[Image content not supported - omitted]")
        # tool_use and tool_result are handled separately in translate_messages
    
    return "\n".join(text_parts)


def extract_tool_uses(content) -> List[dict]:
    """Extract tool_use blocks from content."""
    if isinstance(content, str):
        return []
    
    tool_uses = []
    for block in content:
        if isinstance(block, ToolUseContent):
            tool_uses.append({
                "id": block.id,
                "name": block.name,
                "input": block.input
            })
        elif isinstance(block, dict) and block.get("type") == "tool_use":
            tool_uses.append({
                "id": block.get("id", ""),
                "name": block.get("name", ""),
                "input": block.get("input", {})
            })
    return tool_uses


def extract_tool_results(content) -> List[dict]:
    """
    Extract tool_result blocks from content.
    
    Applies truncation if enabled to prevent context length exceeded errors.
    """
    if isinstance(content, str):
        return []
    
    tool_results = []
    for block in content:
        if isinstance(block, ToolResultContent):
            result_content = block.content
            if not isinstance(result_content, str):
                result_content = extract_text_from_content(result_content)
            
            # Apply truncation to tool results
            result_content = truncate_content(
                result_content,
                settings.max_tool_result_chars,
                context=f"tool_result:{block.tool_use_id[:16]}..."
            )
            
            tool_results.append({
                "tool_use_id": block.tool_use_id,
                "content": result_content,
                "is_error": block.is_error
            })
        elif isinstance(block, dict) and block.get("type") == "tool_result":
            result_content = block.get("content", "")
            if not isinstance(result_content, str):
                result_content = extract_text_from_content(result_content)
            
            tool_use_id = block.get("tool_use_id", "unknown")
            # Apply truncation to tool results
            result_content = truncate_content(
                result_content,
                settings.max_tool_result_chars,
                context=f"tool_result:{tool_use_id[:16]}..."
            )
            
            tool_results.append({
                "tool_use_id": tool_use_id,
                "content": result_content,
                "is_error": block.get("is_error", False)
            })
    return tool_results


def translate_messages(messages: List[Message]) -> List[CerebrasMessage]:
    """
    Translate Anthropic messages to Cerebras/OpenAI format.
    
    CRITICAL: Properly handle tool_use and tool_result:
    
    Anthropic format:
        - assistant: [{"type": "tool_use", "id": "...", "name": "...", "input": {...}}]
        - user: [{"type": "tool_result", "tool_use_id": "...", "content": "..."}]
    
    OpenAI/Cerebras format:
        - assistant: {"role": "assistant", "tool_calls": [{"id": "...", "type": "function", "function": {"name": "...", "arguments": "..."}}]}
        - tool: {"role": "tool", "tool_call_id": "...", "content": "..."}  <- One message per tool result
    """
    from app.models.cerebras import CerebrasToolCall
    import json
    
    cerebras_messages = []
    
    for msg in messages:
        if msg.role == "assistant":
            # Check for tool_use blocks
            tool_uses = extract_tool_uses(msg.content)
            text_content = extract_text_from_content(msg.content)
            
            if tool_uses:
                # Assistant message with tool calls
                tool_calls = [
                    CerebrasToolCall(
                        id=tu["id"],
                        type="function",
                        function={
                            "name": tu["name"],
                            "arguments": json.dumps(tu["input"])
                        }
                    )
                    for tu in tool_uses
                ]
                cerebras_messages.append(CerebrasMessage(
                    role="assistant",
                    content=text_content if text_content else None,
                    tool_calls=tool_calls
                ))
            else:
                # Regular assistant message
                cerebras_messages.append(CerebrasMessage(
                    role="assistant",
                    content=text_content
                ))
        
        elif msg.role == "user":
            # Check for tool_result blocks
            tool_results = extract_tool_results(msg.content)
            text_content = extract_text_from_content(msg.content)
            
            if tool_results:
                # Create separate tool messages for each result (OpenAI format)
                for tr in tool_results:
                    content = tr["content"]
                    if tr["is_error"]:
                        content = f"Error: {content}"
                    cerebras_messages.append(CerebrasMessage(
                        role="tool",
                        content=content,
                        tool_call_id=tr["tool_use_id"]
                    ))
                
                # If there's also text content, add a user message
                if text_content:
                    cerebras_messages.append(CerebrasMessage(
                        role="user",
                        content=text_content
                    ))
            else:
                # Regular user message
                cerebras_messages.append(CerebrasMessage(
                    role="user",
                    content=text_content
                ))
        
        else:
            # System or other roles
            content = extract_text_from_content(msg.content)
            cerebras_messages.append(CerebrasMessage(
                role=msg.role,
                content=content
            ))
    
    return cerebras_messages


def build_system_message(system: Optional[str], behavioral_prefix: str = "") -> Optional[CerebrasMessage]:
    system_text = ""
    
    if isinstance(system, list):
        system_text = "\n".join(
            block.text if isinstance(block, TextContent) else block.get("text", "")
            for block in system
        )
    elif isinstance(system, str):
        system_text = system
    
    if behavioral_prefix:
        combined = f"{behavioral_prefix}\n\n{system_text}" if system_text else behavioral_prefix
    else:
        combined = system_text
    
    if combined:
        return CerebrasMessage(role="system", content=combined)
    return None


def translate_tools(tools) -> Optional[List[CerebrasTool]]:
    """
    Translate Anthropic tools to Cerebras (OpenAI) format.
    
    Anthropic format:
        {"name": "...", "description": "...", "input_schema": {...}}
    
    OpenAI/Cerebras format:
        {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
    """
    if not tools:
        return None
    
    cerebras_tools = []
    for tool in tools:
        cerebras_tool = CerebrasTool(
            type="function",
            function={
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema
            }
        )
        cerebras_tools.append(cerebras_tool)
    
    return cerebras_tools


def translate_tool_choice(tool_choice) -> Optional[str]:
    """
    Translate Anthropic tool_choice to Cerebras format.
    
    Anthropic: {"type": "auto"|"any"|"tool", "name": "..."}
    Cerebras/OpenAI: "auto"|"none"|"required" or {"type": "function", "function": {"name": "..."}}
    """
    if not tool_choice:
        return None
    
    if tool_choice.type == "auto":
        return "auto"
    elif tool_choice.type == "any":
        return "required"  # "any" in Anthropic means "must use a tool" = "required" in OpenAI
    elif tool_choice.type == "tool" and tool_choice.name:
        # Specific tool requested
        return {"type": "function", "function": {"name": tool_choice.name}}
    
    return "auto"


def translate_request(
    request: AnthropicMessagesRequest,
    behavioral_prefix: str = ""
) -> CerebrasChatRequest:
    messages = []
    
    system_msg = build_system_message(request.system, behavioral_prefix)
    if system_msg:
        messages.append(system_msg)
    
    messages.extend(translate_messages(request.messages))
    
    # Apply conversation truncation if enabled
    if settings.truncation_enabled:
        messages_dicts = [m.model_dump() for m in messages]
        truncated_dicts, tokens_used, was_truncated = truncate_conversation(
            messages_dicts,
            max_tokens=settings.context_limit_tokens
        )
        
        if was_truncated:
            logger.info(
                "Applied conversation truncation",
                tokens_after=tokens_used,
                max_tokens=settings.context_limit_tokens
            )
            # Convert back to CerebrasMessage objects
            messages = [CerebrasMessage(**m) for m in truncated_dicts]
    
    cerebras_model = get_cerebras_model(request.model)
    
    stop = None
    if request.stop_sequences:
        stop = request.stop_sequences if len(request.stop_sequences) > 1 else request.stop_sequences[0]
    
    # Translate tools if present
    cerebras_tools = translate_tools(request.tools)
    cerebras_tool_choice = translate_tool_choice(request.tool_choice)
    
    return CerebrasChatRequest(
        model=cerebras_model,
        messages=messages,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
        stop=stop,
        stream=request.stream,
        tools=cerebras_tools,
        tool_choice=cerebras_tool_choice
    )
