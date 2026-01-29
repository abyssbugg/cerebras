import json
import uuid
from typing import Optional, List
from app.models.anthropic import (
    AnthropicMessagesResponse,
    ResponseContentBlock,
    Usage,
)
from app.models.cerebras import CerebrasChatResponse


def translate_finish_reason(cerebras_reason: Optional[str]) -> Optional[str]:
    """
    Translate Cerebras finish reason to Anthropic format.
    
    Cerebras/OpenAI: stop, length, tool_calls
    Anthropic: end_turn, max_tokens, tool_use
    """
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",  # Tool calling
    }
    return mapping.get(cerebras_reason) if cerebras_reason else None


def translate_tool_calls_to_content(tool_calls) -> List[ResponseContentBlock]:
    """
    Translate Cerebras/OpenAI tool_calls to Anthropic tool_use content blocks.
    
    OpenAI format:
        {"id": "...", "type": "function", "function": {"name": "...", "arguments": "{...}"}}
    
    Anthropic format:
        {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
    """
    content_blocks = []
    
    for tool_call in tool_calls:
        # Parse arguments (they come as JSON string in OpenAI format)
        try:
            input_dict = json.loads(tool_call.function.get("arguments", "{}"))
        except json.JSONDecodeError:
            input_dict = {}
        
        content_blocks.append(ResponseContentBlock(
            type="tool_use",
            id=tool_call.id,
            name=tool_call.function.get("name", ""),
            input=input_dict
        ))
    
    return content_blocks


def translate_response(
    cerebras_response: CerebrasChatResponse,
    original_model: str
) -> AnthropicMessagesResponse:
    """
    Translate Cerebras response to Anthropic format.
    CRITICAL: Always echo back the original_model requested by the user.
    
    Handles both text responses and tool calls.
    """
    choice = cerebras_response.choices[0] if cerebras_response.choices else None
    
    content: List[ResponseContentBlock] = []
    
    if choice and choice.message:
        # Handle text content
        content_text = choice.message.text
        if content_text:
            content.append(ResponseContentBlock(type="text", text=content_text))
        
        # Handle tool calls (OpenAI -> Anthropic translation)
        if choice.message.tool_calls:
            tool_content = translate_tool_calls_to_content(choice.message.tool_calls)
            content.extend(tool_content)
    
    # Ensure we have at least empty text content
    if not content:
        content = [ResponseContentBlock(type="text", text="")]
    
    return AnthropicMessagesResponse(
        id=f"msg_{uuid.uuid4().hex[:24]}",
        type="message",
        role="assistant",
        content=content,
        model=original_model,  # CRITICAL: Echo back requested model
        stop_reason=translate_finish_reason(choice.finish_reason if choice else None),
        stop_sequence=None,
        usage=Usage(
            input_tokens=cerebras_response.usage.prompt_tokens,
            output_tokens=cerebras_response.usage.completion_tokens
        )
    )
