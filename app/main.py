from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes import messages, token_count, health
from app.api.middleware.auth import AuthMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.middleware.validation import ValidationMiddleware
from app.utils.logging import setup_logging, get_logger
from app.utils.metrics import setup_metrics, track_active_connections
from starlette.middleware.base import BaseHTTPMiddleware

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    
    # In passthrough mode, CEREBRAS_API_KEY is not required (users provide their own)
    # Only validate if gateway keys are configured (non-passthrough mode)
    if settings.gateway_api_keys and not settings.cerebras_api_key:
        logger.error("CEREBRAS_API_KEY is required when GATEWAY_API_KEYS is set")
        raise RuntimeError(
            "Missing required configuration: CEREBRAS_API_KEY must be set "
            "when using gateway API keys mode."
        )
    
    # Determine auth mode
    if settings.gateway_api_keys:
        auth_mode = "gateway_keys"
        logger.info("Running in gateway keys mode (users use gateway API keys)")
    else:
        auth_mode = "passthrough"
        logger.info("Running in passthrough mode (users provide their own Cerebras API key)")
    
    logger.info(
        "Starting Cerebras Anthropic Gateway",
        environment=settings.environment,
        auth_mode=auth_mode,
        cerebras_base_url=settings.cerebras_base_url,
        rate_limiting=settings.rate_limit_enabled,
        caching=settings.cache_enabled
    )
    
    yield
    
    logger.info("Shutting down Cerebras Anthropic Gateway")


app = FastAPI(
    title="Cerebras Anthropic Gateway",
    description="Drop-in Anthropic API replacement backed by Cerebras",
    version="1.0.0",
    lifespan=lifespan,
)

# Add middleware (must be done before app startup)
# CORS: Parse origins from settings (comma-separated string or "*" for all)
cors_origins = (
    ["*"] if settings.cors_origins == "*" 
    else [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)
app.add_middleware(ValidationMiddleware)

if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)

# Add metrics middleware for tracking active connections
app.add_middleware(BaseHTTPMiddleware, dispatch=track_active_connections)

# Include routers at multiple paths for compatibility
# Standard Anthropic path: /v1/messages
app.include_router(health.router, tags=["Health"])
app.include_router(messages.router, prefix="/v1", tags=["Messages"])
app.include_router(token_count.router, prefix="/v1", tags=["Token Count"])

# GLM/MiniMax-style path: /anthropic/v1/messages
# This allows users to set ANTHROPIC_BASE_URL=https://cerebras.onrender.com/anthropic
app.include_router(messages.router, prefix="/anthropic/v1", tags=["Messages (Anthropic)"])
app.include_router(token_count.router, prefix="/anthropic/v1", tags=["Token Count (Anthropic)"])

# Setup metrics endpoint (can be done at module level)
setup_metrics(app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
