import json
from typing import Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.models.errors import AnthropicError, ErrorDetail
from app.utils.logging import get_logger

logger = get_logger(__name__)

MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
MAX_MESSAGES = 1000
MAX_MESSAGE_LENGTH = 1 * 1024 * 1024  # 1MB per message
MAX_SYSTEM_LENGTH = 1 * 1024 * 1024  # 1MB for system prompt

EXEMPT_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


class ValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip validation for exempt paths
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        
        # Skip validation for non-POST requests
        if request.method != "POST":
            return await call_next(request)
        
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_CONTENT_LENGTH:
                    logger.warning(
                        "Request too large",
                        content_length=content_length
                    )
                    return JSONResponse(
                        status_code=413,
                        content=AnthropicError(
                            error=ErrorDetail(
                                type="invalid_request_error",
                                message=f"Request body too large. Maximum size is {MAX_CONTENT_LENGTH} bytes."
                            )
                        ).model_dump()
                    )
            except ValueError:
                pass
        
        # Check content type
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            logger.warning(
                "Invalid content type",
                content_type=content_type
            )
            return JSONResponse(
                status_code=415,
                content=AnthropicError(
                    error=ErrorDetail(
                        type="invalid_request_error",
                        message="Content-Type must be application/json"
                    )
                ).model_dump()
            )
        
        # CRITICAL: Validate message-specific fields for /v1/messages endpoints
        # Check both standard and anthropic-prefixed paths
        messages_paths = {"/v1/messages", "/anthropic/v1/messages"}
        if request.url.path in messages_paths:
            validation_error = await self._validate_messages_request(request)
            if validation_error:
                return validation_error
        
        return await call_next(request)
    
    async def _validate_messages_request(self, request: Request) -> Optional[JSONResponse]:
        """
        Validate messages endpoint specific constraints.
        CRITICAL: Enforce MAX_MESSAGES and MAX_MESSAGE_LENGTH limits.
        
        Note: FastAPI/Starlette caches the body internally, so reading it here
        doesn't prevent it from being read again by the route handler. We also
        store the parsed JSON in request.state for potential reuse.
        """
        try:
            # Read and parse body (Starlette caches this internally)
            body = await request.body()
            data = json.loads(body)
            
            # Store parsed body in request state for potential reuse
            request.state.validated_body = data
            
            # Validate messages array
            messages = data.get("messages", [])
            
            # Check message count
            if len(messages) > MAX_MESSAGES:
                logger.warning(
                    "Too many messages",
                    message_count=len(messages),
                    max_allowed=MAX_MESSAGES
                )
                return JSONResponse(
                    status_code=400,
                    content=AnthropicError(
                        error=ErrorDetail(
                            type="invalid_request_error",
                            message=f"Too many messages. Maximum is {MAX_MESSAGES} messages per request."
                        )
                    ).model_dump()
                )
            
            # Check individual message lengths
            for idx, msg in enumerate(messages):
                content = msg.get("content", "")
                content_str = json.dumps(content) if not isinstance(content, str) else content
                
                if len(content_str) > MAX_MESSAGE_LENGTH:
                    logger.warning(
                        "Message too long",
                        message_index=idx,
                        length=len(content_str),
                        max_allowed=MAX_MESSAGE_LENGTH
                    )
                    return JSONResponse(
                        status_code=400,
                        content=AnthropicError(
                            error=ErrorDetail(
                                type="invalid_request_error",
                                message=f"Message at index {idx} is too long. Maximum length is {MAX_MESSAGE_LENGTH} characters."
                            )
                        ).model_dump()
                    )
            
            # Check system prompt length
            system = data.get("system", "")
            if system and len(system) > MAX_SYSTEM_LENGTH:
                logger.warning(
                    "System prompt too long",
                    length=len(system),
                    max_allowed=MAX_SYSTEM_LENGTH
                )
                return JSONResponse(
                    status_code=400,
                    content=AnthropicError(
                        error=ErrorDetail(
                            type="invalid_request_error",
                            message=f"System prompt is too long. Maximum length is {MAX_SYSTEM_LENGTH} characters."
                        )
                    ).model_dump()
                )
            
            return None
            
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in request body")
            return JSONResponse(
                status_code=400,
                content=AnthropicError(
                    error=ErrorDetail(
                        type="invalid_request_error",
                        message="Request body must be valid JSON"
                    )
                ).model_dump()
            )
        except Exception as e:
            logger.error("Validation error", error=str(e))
            return JSONResponse(
                status_code=400,
                content=AnthropicError(
                    error=ErrorDetail(
                        type="invalid_request_error",
                        message=f"Validation error: {str(e)}"
                    )
                ).model_dump()
            )
