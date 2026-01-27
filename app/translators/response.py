import uuid
from typing import Optional
from app.models.anthropic import (
    AnthropicMessagesResponse,
    ResponseContentBlock,
    Usage,
)
from app.models.cerebras import CerebrasChatResponse


def translate_finish_reason(cerebras_reason: Optional[str]) -> Optional[str]:
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
    }
    return mapping.get(cerebras_reason) if cerebras_reason else None


def translate_response(
    cerebras_response: CerebrasChatResponse,
    original_model: str
) -> AnthropicMessagesResponse:
    """
    Translate Cerebras response to Anthropic format.
    CRITICAL: Always echo back the original_model requested by the user.
    """
    choice = cerebras_response.choices[0] if cerebras_response.choices else None
    
    content_text = choice.message.content if choice and choice.message else ""
    
    content = [ResponseContentBlock(type="text", text=content_text)]
    
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
