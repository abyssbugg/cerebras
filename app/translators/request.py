from typing import List, Optional
from app.models.anthropic import (
    AnthropicMessagesRequest,
    Message,
    TextContent,
    ImageContent,
    ToolUseContent,
    ToolResultContent,
)
from app.models.cerebras import CerebrasMessage, CerebrasChatRequest
from app.config import get_settings

settings = get_settings()

MODEL_MAPPING = {
    "claude-3-5-sonnet-20241022": "llama-3.3-70b",
    "claude-3-5-sonnet-latest": "llama-3.3-70b",
    "claude-sonnet-4-20250514": "llama-3.3-70b",
    "claude-sonnet-4": "llama-3.3-70b",
    "claude-3-5-haiku-20241022": "llama-3.1-8b",
    "claude-3-5-haiku-latest": "llama-3.1-8b",
    "claude-3-opus-20240229": "llama-3.3-70b",
    "claude-3-opus-latest": "llama-3.3-70b",
    "claude-3-haiku-20240307": "llama-3.1-8b",
}


def get_cerebras_model(anthropic_model: str) -> str:
    return MODEL_MAPPING.get(anthropic_model, settings.cerebras_model)


def extract_text_from_content(content) -> str:
    if isinstance(content, str):
        return content
    
    text_parts = []
    for block in content:
        if isinstance(block, TextContent) or (isinstance(block, dict) and block.get("type") == "text"):
            text = block.text if isinstance(block, TextContent) else block.get("text", "")
            text_parts.append(text)
        elif isinstance(block, ToolResultContent) or (isinstance(block, dict) and block.get("type") == "tool_result"):
            result_content = block.content if isinstance(block, ToolResultContent) else block.get("content", "")
            if isinstance(result_content, str):
                text_parts.append(f"[Tool Result]: {result_content}")
            else:
                text_parts.append(f"[Tool Result]: {extract_text_from_content(result_content)}")
        elif isinstance(block, ToolUseContent) or (isinstance(block, dict) and block.get("type") == "tool_use"):
            name = block.name if isinstance(block, ToolUseContent) else block.get("name", "unknown")
            input_data = block.input if isinstance(block, ToolUseContent) else block.get("input", {})
            text_parts.append(f"[Tool Use: {name}]: {input_data}")
        elif isinstance(block, ImageContent) or (isinstance(block, dict) and block.get("type") == "image"):
            text_parts.append("[Image content not supported by Cerebras - omitted]")
    
    return "\n".join(text_parts)


def translate_messages(messages: List[Message]) -> List[CerebrasMessage]:
    cerebras_messages = []
    
    for msg in messages:
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


def translate_request(
    request: AnthropicMessagesRequest,
    behavioral_prefix: str = ""
) -> CerebrasChatRequest:
    messages = []
    
    system_msg = build_system_message(request.system, behavioral_prefix)
    if system_msg:
        messages.append(system_msg)
    
    messages.extend(translate_messages(request.messages))
    
    cerebras_model = get_cerebras_model(request.model)
    
    stop = None
    if request.stop_sequences:
        stop = request.stop_sequences if len(request.stop_sequences) > 1 else request.stop_sequences[0]
    
    return CerebrasChatRequest(
        model=cerebras_model,
        messages=messages,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
        stop=stop,
        stream=request.stream
    )
