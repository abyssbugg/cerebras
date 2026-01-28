from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional

from app.models.anthropic import AnthropicMessagesRequest
from app.models.errors import AnthropicError, ErrorDetail, APIError, InvalidRequestError
from app.translators.request import translate_request
from app.translators.response import translate_response
from app.translators.streaming import translate_stream
from app.translators.prompt_tuning import get_behavioral_prefix, adjust_temperature
from app.translators.response_enhancer import enhance_response
from app.clients.cerebras import get_cerebras_client
from app.services.cache_service import get_cache_service
# model_router is available but not currently used (intelligent routing is optional)
# from app.services.model_router import get_optimal_model
from app.utils.logging import get_logger
from app.utils.metrics import (
    REQUEST_COUNT,
    REQUEST_LATENCY,
    TOKENS_PROCESSED,
)
from app.utils.schema_validator import validate_response, validate_streaming_event
import time

router = APIRouter()
logger = get_logger(__name__)


@router.post("/messages")
async def create_message(
    http_request: Request,
    request: AnthropicMessagesRequest,
    anthropic_version: Optional[str] = Header(None, alias="anthropic-version"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    start_time = time.time()
    original_model = request.model
    
    # Get the API key to use for Cerebras (set by auth middleware)
    # In passthrough mode, this is the user's Cerebras key
    # In gateway mode, this is the server's Cerebras key
    cerebras_api_key = getattr(http_request.state, 'cerebras_api_key', None)
    auth_mode = getattr(http_request.state, 'auth_mode', 'unknown')
    
    try:
        logger.info(
            "Processing messages request",
            model=original_model,
            stream=request.stream,
            max_tokens=request.max_tokens,
            auth_mode=auth_mode
        )
        
        # Get behavioral prefix for system prompt (PREFIX, never overwrite)
        behavioral_prefix = get_behavioral_prefix(request.messages)
        
        # Adjust temperature for code tasks
        adjusted_temp = adjust_temperature(request.temperature, request.messages)
        request.temperature = adjusted_temp
        
        # Translate to Cerebras format
        cerebras_request = translate_request(request, behavioral_prefix)
        
        # Get cache service
        cache_service = get_cache_service()
        
        client = get_cerebras_client()
        
        if request.stream:
            # Streaming response - pass API key to stream
            async def generate_stream():
                try:
                    stream = client.chat_completion_stream(cerebras_request, api_key=cerebras_api_key)
                    async for event in translate_stream(stream, original_model):
                        # Validate each SSE event
                        validate_streaming_event(event)
                        yield event
                except Exception as e:
                    logger.error("Streaming error", error=str(e))
                    # Use json.dumps to ensure proper JSON formatting
                    import json as json_lib
                    error_data = json_lib.dumps({"error": str(e)})
                    error_event = f"event: error\ndata: {error_data}\n\n"
                    # Validate error event before yielding
                    validate_streaming_event(error_event)
                    yield error_event
            
            REQUEST_COUNT.labels(
                method="POST",
                endpoint="/v1/messages",
                status="200"
            ).inc()
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        else:
            # Check cache for deterministic requests
            cache_key = None
            if cache_service and request.temperature is not None and request.temperature <= 0.1:
                cache_key = cache_service.generate_cache_key(request)
                cached = await cache_service.get(cache_key)
                if cached:
                    logger.info("Cache hit", cache_key=cache_key[:32])
                    REQUEST_COUNT.labels(
                        method="POST",
                        endpoint="/v1/messages",
                        status="200"
                    ).inc()
                    return JSONResponse(content=cached)
            
            # Non-streaming response - pass API key to client
            cerebras_response = await client.chat_completion(cerebras_request, api_key=cerebras_api_key)
            
            # Translate response (CRITICAL: pass original_model for echo-back)
            anthropic_response = translate_response(cerebras_response, original_model)
            
            # Enhance response (formatting)
            anthropic_response = enhance_response(anthropic_response)
            
            # Validate response against schema
            response_dict = anthropic_response.model_dump()
            validate_response(response_dict)
            
            # Cache if applicable
            if cache_key and cache_service:
                await cache_service.set(cache_key, response_dict)
            
            # Metrics
            latency = time.time() - start_time
            REQUEST_LATENCY.labels(endpoint="/v1/messages").observe(latency)
            REQUEST_COUNT.labels(
                method="POST",
                endpoint="/v1/messages",
                status="200"
            ).inc()
            TOKENS_PROCESSED.labels(type="input").inc(anthropic_response.usage.input_tokens)
            TOKENS_PROCESSED.labels(type="output").inc(anthropic_response.usage.output_tokens)
            
            logger.info(
                "Request completed",
                latency_ms=latency * 1000,
                input_tokens=anthropic_response.usage.input_tokens,
                output_tokens=anthropic_response.usage.output_tokens
            )
            
            return JSONResponse(content=response_dict)
    
    except InvalidRequestError as e:
        logger.warning("Invalid request", error=e.message)
        REQUEST_COUNT.labels(
            method="POST",
            endpoint="/v1/messages",
            status="400"
        ).inc()
        return JSONResponse(
            status_code=400,
            content=AnthropicError(
                error=ErrorDetail(type="invalid_request_error", message=e.message)
            ).model_dump()
        )
    
    except APIError as e:
        logger.error("API error", error=e.message, status_code=e.status_code)
        REQUEST_COUNT.labels(
            method="POST",
            endpoint="/v1/messages",
            status=str(e.status_code)
        ).inc()
        return JSONResponse(
            status_code=e.status_code,
            content=AnthropicError(
                error=ErrorDetail(type="api_error", message=e.message)
            ).model_dump()
        )
    
    except Exception as e:
        logger.error("Unexpected error", error=str(e), exc_info=True)
        REQUEST_COUNT.labels(
            method="POST",
            endpoint="/v1/messages",
            status="500"
        ).inc()
        return JSONResponse(
            status_code=500,
            content=AnthropicError(
                error=ErrorDetail(type="api_error", message="Internal server error")
            ).model_dump()
        )
