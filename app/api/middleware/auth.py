from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import get_settings
from app.models.errors import AnthropicError, ErrorDetail
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

EXEMPT_PATHS = {"/", "/health", "/metrics", "/docs", "/openapi.json", "/redoc"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for exempt paths
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        
        # Get API key from header
        api_key = request.headers.get(settings.api_key_header)
        
        if not api_key:
            logger.warning("Missing API key", path=request.url.path)
            return JSONResponse(
                status_code=401,
                content=AnthropicError(
                    error=ErrorDetail(
                        type="authentication_error",
                        message="Missing API key"
                    )
                ).model_dump()
            )
        
        # Validate API key if gateway keys are configured
        if settings.gateway_api_keys:
            valid_keys = [k.strip() for k in settings.gateway_api_keys.split(",")]
            if api_key not in valid_keys:
                logger.warning("Invalid API key", path=request.url.path)
                return JSONResponse(
                    status_code=401,
                    content=AnthropicError(
                        error=ErrorDetail(
                            type="authentication_error",
                            message="Invalid API key"
                        )
                    ).model_dump()
                )
        
        # Store API key in request state for downstream use
        request.state.api_key = api_key
        
        return await call_next(request)
