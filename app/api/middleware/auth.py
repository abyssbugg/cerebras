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
    """
    Authentication middleware supporting two modes:
    
    1. Gateway Keys Mode (GATEWAY_API_KEYS is set):
       - Users authenticate with gateway-issued keys
       - Server uses its own CEREBRAS_API_KEY for backend calls
       
    2. Passthrough Mode (GATEWAY_API_KEYS is empty):
       - Users provide their own Cerebras API key directly
       - Like GLM/MiniMax - users just set their Cerebras key as the auth token
       - The key is passed through to Cerebras API calls
    """
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for exempt paths
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        
        # Get API key from header (supports both x-api-key and Authorization: Bearer)
        api_key = request.headers.get(settings.api_key_header)
        
        # Also check Authorization header (some clients use this)
        if not api_key:
            auth_header = request.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                api_key = auth_header[7:]  # Remove "Bearer " prefix
        
        if not api_key:
            logger.warning("Missing API key", path=request.url.path)
            return JSONResponse(
                status_code=401,
                content=AnthropicError(
                    error=ErrorDetail(
                        type="authentication_error",
                        message="Missing API key. Provide your Cerebras API key in the x-api-key header."
                    )
                ).model_dump()
            )
        
        # Determine which API key to use for Cerebras calls
        if settings.gateway_api_keys:
            # Gateway Keys Mode: validate against configured keys
            valid_keys = [k.strip() for k in settings.gateway_api_keys.split(",")]
            if api_key not in valid_keys:
                logger.warning("Invalid gateway API key", path=request.url.path)
                return JSONResponse(
                    status_code=401,
                    content=AnthropicError(
                        error=ErrorDetail(
                            type="authentication_error",
                            message="Invalid API key"
                        )
                    ).model_dump()
                )
            # Use server's Cerebras API key
            request.state.cerebras_api_key = settings.cerebras_api_key
            request.state.auth_mode = "gateway"
        else:
            # Passthrough Mode: user's key is their Cerebras API key
            # Like GLM/MiniMax - the key they provide IS the Cerebras key
            request.state.cerebras_api_key = api_key
            request.state.auth_mode = "passthrough"
        
        # Store original API key for logging/tracking
        request.state.api_key = api_key
        
        return await call_next(request)
