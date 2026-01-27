import json
import hashlib
from typing import Optional, Any
from app.config import get_settings
from app.models.anthropic import AnthropicMessagesRequest
from app.utils.logging import get_logger
from app.utils.metrics import CACHE_HITS, CACHE_MISSES

settings = get_settings()
logger = get_logger(__name__)


class CacheService:
    def __init__(self):
        self.redis_client = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis client if available."""
        if not settings.cache_enabled:
            return
        
        try:
            import redis.asyncio as redis
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
            logger.info("Redis cache service initialized")
        except Exception as e:
            logger.warning(
                "Redis unavailable, caching disabled",
                error=str(e)
            )
    
    def generate_cache_key(self, request: AnthropicMessagesRequest) -> str:
        """
        Generate cache key from request.
        
        CRITICAL: Include ALL request fields that affect output to prevent cache collisions.
        """
        # Convert messages to deterministic format
        messages = []
        for m in request.messages:
            # Handle content whether it's str or list
            if isinstance(m.content, list):
                content = json.dumps([c.model_dump() if hasattr(c, 'model_dump') else c for c in m.content], sort_keys=True)
            else:
                content = str(m.content)
            messages.append({"role": m.role, "content": content})
        
        # Create deterministic hash from ALL relevant request fields
        key_data = {
            "model": request.model,
            "messages": messages,
            "system": str(request.system) if request.system else None,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "top_k": request.top_k,
            "stop_sequences": sorted(request.stop_sequences) if request.stop_sequences else None,
            "stream": request.stream,  # Include stream flag
            "metadata": json.dumps(request.metadata, sort_keys=True) if request.metadata else None,
        }
        
        # Use sorted JSON to ensure deterministic hashing
        key_str = json.dumps(key_data, sort_keys=True)
        hash_key = hashlib.sha256(key_str.encode()).hexdigest()
        
        return f"response_cache:{hash_key}"
    
    async def get(self, key: str) -> Optional[dict]:
        """Get cached response."""
        if not self.redis_client:
            return None
        
        try:
            cached = await self.redis_client.get(key)
            if cached:
                CACHE_HITS.inc()
                return json.loads(cached)
            CACHE_MISSES.inc()
            return None
        except Exception as e:
            logger.warning("Cache get error", error=str(e))
            CACHE_MISSES.inc()
            return None
    
    async def set(self, key: str, value: dict, ttl: Optional[int] = None) -> bool:
        """Set cached response."""
        if not self.redis_client:
            return False
        
        ttl = ttl or settings.cache_ttl_seconds
        
        try:
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(value)
            )
            logger.debug("Response cached", key=key[:32])
            return True
        except Exception as e:
            logger.warning("Cache set error", error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete cached response."""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.warning("Cache delete error", error=str(e))
            return False


_cache_service: Optional[CacheService] = None


def get_cache_service() -> Optional[CacheService]:
    """Get cache service singleton."""
    global _cache_service
    
    if not settings.cache_enabled:
        return None
    
    if _cache_service is None:
        _cache_service = CacheService()
    
    return _cache_service
