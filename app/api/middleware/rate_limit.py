import time
import threading
from typing import Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import get_settings
from app.models.errors import AnthropicError, ErrorDetail
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# In-memory rate limiting (fallback when Redis unavailable)
# Thread-safe with lock for concurrent access
_rate_limit_store: dict = {}
_rate_limit_lock = threading.Lock()

EXEMPT_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.redis_client: Optional[object] = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis client if available."""
        if not settings.rate_limit_enabled:
            return
        
        try:
            import redis.asyncio as redis
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
            logger.info("Redis rate limiter initialized")
        except Exception as e:
            logger.warning(
                "Redis unavailable, using in-memory rate limiting",
                error=str(e)
            )
    
    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)
        
        # Skip rate limiting for exempt paths
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        
        # Get identifier (API key or IP)
        # CRITICAL: Handle None case when request.client is None (e.g., test clients)
        identifier = getattr(request.state, 'api_key', None)
        if not identifier:
            identifier = request.client.host if request.client else "unknown"
        
        # Ensure identifier is never None
        if not identifier:
            identifier = "unknown-client"
        
        # Check rate limit
        is_limited, retry_after = await self._check_rate_limit(identifier)
        
        if is_limited:
            safe_identifier = identifier[:16] + "..." if len(identifier) > 16 else identifier
            logger.warning("Rate limit exceeded", identifier=safe_identifier)
            return JSONResponse(
                status_code=429,
                content=AnthropicError(
                    error=ErrorDetail(
                        type="rate_limit_error",
                        message=f"Rate limit exceeded. Retry after {retry_after} seconds."
                    )
                ).model_dump(),
                headers={"Retry-After": str(retry_after)}
            )
        
        return await call_next(request)
    
    async def _check_rate_limit(self, identifier: str) -> tuple[bool, int]:
        """Check if identifier has exceeded rate limit."""
        window_seconds = 60
        max_requests = settings.rate_limit_requests_per_minute
        
        if self.redis_client:
            return await self._check_redis_rate_limit(
                identifier, window_seconds, max_requests
            )
        else:
            return self._check_memory_rate_limit(
                identifier, window_seconds, max_requests
            )
    
    async def _check_redis_rate_limit(
        self,
        identifier: str,
        window_seconds: int,
        max_requests: int
    ) -> tuple[bool, int]:
        """Redis-backed sliding window rate limiting."""
        try:
            key = f"rate_limit:{identifier}"
            current_time = int(time.time())
            window_start = current_time - window_seconds
            
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(current_time): current_time})
            pipe.zcard(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()
            
            request_count = results[2]
            
            if request_count > max_requests:
                return True, window_seconds
            
            return False, 0
        except Exception as e:
            logger.warning("Redis rate limit check failed", error=str(e))
            return self._check_memory_rate_limit(
                identifier, window_seconds, max_requests
            )
    
    def _check_memory_rate_limit(
        self,
        identifier: str,
        window_seconds: int,
        max_requests: int
    ) -> tuple[bool, int]:
        """In-memory sliding window rate limiting (fallback).
        
        Thread-safe implementation using a lock to protect
        concurrent access to the shared rate limit store.
        """
        current_time = time.time()
        window_start = current_time - window_seconds
        
        with _rate_limit_lock:
            # Initialize if needed
            if identifier not in _rate_limit_store:
                _rate_limit_store[identifier] = []
            
            # Remove old requests
            _rate_limit_store[identifier] = [
                ts for ts in _rate_limit_store[identifier]
                if ts > window_start
            ]
            
            # Check limit
            if len(_rate_limit_store[identifier]) >= max_requests:
                return True, window_seconds
            
            # Add current request
            _rate_limit_store[identifier].append(current_time)
            
            return False, 0
