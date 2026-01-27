from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.models.anthropic import AnthropicTokenCountRequest, AnthropicTokenCountResponse
from app.models.errors import AnthropicError, ErrorDetail
from app.utils.tokenizer import count_tokens
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/messages/count_tokens")
async def count_message_tokens(request: AnthropicTokenCountRequest):
    """
    Best-effort token count estimation using tiktoken (cl100k_base).
    Note: This is an approximation - actual token counts may vary.
    """
    try:
        total_tokens = 0
        
        # Count system prompt tokens
        if request.system:
            if isinstance(request.system, str):
                total_tokens += count_tokens(request.system)
            else:
                for block in request.system:
                    if hasattr(block, 'text'):
                        total_tokens += count_tokens(block.text)
        
        # Count message tokens
        for message in request.messages:
            if isinstance(message.content, str):
                total_tokens += count_tokens(message.content)
            else:
                for block in message.content:
                    if hasattr(block, 'text'):
                        total_tokens += count_tokens(block.text)
                    elif hasattr(block, 'content'):
                        if isinstance(block.content, str):
                            total_tokens += count_tokens(block.content)
        
        # Count tool tokens if present
        if request.tools:
            for tool in request.tools:
                total_tokens += count_tokens(tool.name)
                total_tokens += count_tokens(tool.description)
                total_tokens += count_tokens(str(tool.input_schema))
        
        # Add overhead for message structure
        total_tokens += len(request.messages) * 4
        
        logger.info("Token count estimated", input_tokens=total_tokens)
        
        return JSONResponse(
            content=AnthropicTokenCountResponse(input_tokens=total_tokens).model_dump()
        )
    
    except Exception as e:
        logger.error("Token count error", error=str(e))
        return JSONResponse(
            status_code=500,
            content=AnthropicError(
                error=ErrorDetail(type="api_error", message="Failed to count tokens")
            ).model_dump()
        )
