"""
Usage Tracker Service - OPTIONAL FEATURE (not currently wired)

This service tracks token usage per API key for monitoring and billing.
To enable: Wire into messages.py after successful completion.

TODO: Call track_usage() in messages.py after each successful request.
"""
from typing import Optional
from datetime import datetime, timedelta
from app.config import get_settings
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class UsageTracker:
    """
    Track API usage per API key for monitoring and billing.
    
    NOTE: Not currently integrated. To use, call track_usage() after each request.
    """
    
    def __init__(self):
        self.redis_client = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis client if available."""
        try:
            import redis.asyncio as redis
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
            logger.info("Usage tracker initialized")
        except Exception as e:
            logger.warning(
                "Redis unavailable, usage tracking disabled",
                error=str(e)
            )
    
    async def track_request(
        self,
        api_key: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        stream: bool = False
    ) -> bool:
        """Track a request's usage."""
        if not self.redis_client:
            return False
        
        try:
            # Hash the API key for privacy
            key_hash = api_key[:8] + "..." if len(api_key) > 8 else api_key
            
            # Get current date for daily aggregation
            today = datetime.utcnow().strftime("%Y-%m-%d")
            
            # Update daily counters
            pipe = self.redis_client.pipeline()
            
            # Request count
            pipe.hincrby(f"usage:{key_hash}:{today}", "requests", 1)
            
            # Token counts
            pipe.hincrby(f"usage:{key_hash}:{today}", "input_tokens", input_tokens)
            pipe.hincrby(f"usage:{key_hash}:{today}", "output_tokens", output_tokens)
            
            # Streaming count
            if stream:
                pipe.hincrby(f"usage:{key_hash}:{today}", "streaming_requests", 1)
            
            # Set expiry (30 days)
            pipe.expire(f"usage:{key_hash}:{today}", 30 * 24 * 60 * 60)
            
            await pipe.execute()
            
            logger.debug(
                "Usage tracked",
                key_hash=key_hash,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
            return True
            
        except Exception as e:
            logger.warning("Usage tracking error", error=str(e))
            return False
    
    async def get_usage(
        self,
        api_key: str,
        date: Optional[str] = None
    ) -> dict:
        """Get usage statistics for an API key."""
        if not self.redis_client:
            return {}
        
        try:
            key_hash = api_key[:8] + "..." if len(api_key) > 8 else api_key
            date = date or datetime.utcnow().strftime("%Y-%m-%d")
            
            usage = await self.redis_client.hgetall(f"usage:{key_hash}:{date}")
            
            return {
                "date": date,
                "requests": int(usage.get("requests", 0)),
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
                "streaming_requests": int(usage.get("streaming_requests", 0)),
            }
            
        except Exception as e:
            logger.warning("Get usage error", error=str(e))
            return {}


_usage_tracker: Optional[UsageTracker] = None


def get_usage_tracker() -> Optional[UsageTracker]:
    """Get usage tracker singleton."""
    global _usage_tracker
    
    if _usage_tracker is None:
        _usage_tracker = UsageTracker()
    
    return _usage_tracker
