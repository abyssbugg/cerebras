from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes import messages, token_count, health
from app.api.middleware.auth import AuthMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.middleware.validation import ValidationMiddleware
from app.utils.logging import setup_logging, get_logger
from app.utils.metrics import setup_metrics

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    setup_metrics(app)
    
    # CRITICAL: Validate required configuration before startup
    if not settings.cerebras_api_key:
        logger.error("CEREBRAS_API_KEY is required but not set")
        raise RuntimeError(
            "Missing required configuration: CEREBRAS_API_KEY must be set. "
            "Please set the CEREBRAS_API_KEY environment variable."
        )
    
    if not settings.gateway_api_keys and settings.environment == "production":
        logger.warning(
            "No gateway API keys configured. Authentication is disabled! "
            "Set GATEWAY_API_KEYS environment variable for production."
        )
    
    logger.info(
        "Starting Cerebras Anthropic Gateway",
        environment=settings.environment,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)
app.add_middleware(ValidationMiddleware)

if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)

app.include_router(health.router, tags=["Health"])
app.include_router(messages.router, prefix="/v1", tags=["Messages"])
app.include_router(token_count.router, prefix="/v1", tags=["Token Count"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
