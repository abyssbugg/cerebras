"""Unit tests for cache service."""
import pytest
import json
from unittest.mock import patch, AsyncMock

from app.services.cache_service import CacheService, get_cache_service
from app.models.anthropic import AnthropicMessagesRequest, Message


class TestCacheKeyGeneration:
    """Tests for cache key generation."""
    
    def test_cache_key_is_deterministic(self):
        """Test that same request generates same cache key."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_ttl_seconds = 3600
            
            service = CacheService()
            service.redis_client = None  # Don't need Redis for key generation
            
            request = AnthropicMessagesRequest(
                model="claude-sonnet-4",
                max_tokens=100,
                messages=[Message(role="user", content="Hello")],
                temperature=0.5
            )
            
            key1 = service.generate_cache_key(request)
            key2 = service.generate_cache_key(request)
            
            assert key1 == key2
    
    def test_different_requests_generate_different_keys(self):
        """Test that different requests generate different cache keys."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_ttl_seconds = 3600
            
            service = CacheService()
            service.redis_client = None
            
            request1 = AnthropicMessagesRequest(
                model="claude-sonnet-4",
                max_tokens=100,
                messages=[Message(role="user", content="Hello")],
                temperature=0.5
            )
            
            request2 = AnthropicMessagesRequest(
                model="claude-sonnet-4",
                max_tokens=100,
                messages=[Message(role="user", content="Goodbye")],
                temperature=0.5
            )
            
            key1 = service.generate_cache_key(request1)
            key2 = service.generate_cache_key(request2)
            
            assert key1 != key2
    
    def test_cache_key_includes_all_relevant_fields(self):
        """Test that cache key considers all relevant request fields."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_ttl_seconds = 3600
            
            service = CacheService()
            service.redis_client = None
            
            base_request = AnthropicMessagesRequest(
                model="claude-sonnet-4",
                max_tokens=100,
                messages=[Message(role="user", content="Hello")],
                temperature=0.5
            )
            
            # Same request but different temperature
            different_temp = AnthropicMessagesRequest(
                model="claude-sonnet-4",
                max_tokens=100,
                messages=[Message(role="user", content="Hello")],
                temperature=0.7
            )
            
            # Same request but different max_tokens
            different_tokens = AnthropicMessagesRequest(
                model="claude-sonnet-4",
                max_tokens=200,
                messages=[Message(role="user", content="Hello")],
                temperature=0.5
            )
            
            key_base = service.generate_cache_key(base_request)
            key_temp = service.generate_cache_key(different_temp)
            key_tokens = service.generate_cache_key(different_tokens)
            
            assert key_base != key_temp
            assert key_base != key_tokens
            assert key_temp != key_tokens
    
    def test_cache_key_format(self):
        """Test that cache key has expected format."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_ttl_seconds = 3600
            
            service = CacheService()
            service.redis_client = None
            
            request = AnthropicMessagesRequest(
                model="claude-sonnet-4",
                max_tokens=100,
                messages=[Message(role="user", content="Hello")]
            )
            
            key = service.generate_cache_key(request)
            
            assert key.startswith("response_cache:")
            # Key should be a SHA256 hash (64 hex characters after prefix)
            hash_part = key.split(":")[1]
            assert len(hash_part) == 64


class TestCacheOperations:
    """Tests for cache get/set operations."""
    
    @pytest.mark.asyncio
    async def test_get_returns_none_when_redis_unavailable(self):
        """Test that get returns None when Redis is not available."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_ttl_seconds = 3600
            
            service = CacheService()
            service.redis_client = None
            
            result = await service.get("test-key")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_set_returns_false_when_redis_unavailable(self):
        """Test that set returns False when Redis is not available."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_ttl_seconds = 3600
            
            service = CacheService()
            service.redis_client = None
            
            result = await service.set("test-key", {"data": "test"})
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_with_mock_redis(self):
        """Test cache get with mocked Redis."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_ttl_seconds = 3600
            
            service = CacheService()
            
            # Mock Redis client
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value='{"key": "value"}')
            service.redis_client = mock_redis
            
            result = await service.get("test-key")
            
            assert result == {"key": "value"}
            mock_redis.get.assert_called_once_with("test-key")
    
    @pytest.mark.asyncio
    async def test_get_returns_none_on_cache_miss(self):
        """Test cache get returns None on cache miss."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_ttl_seconds = 3600
            
            service = CacheService()
            
            # Mock Redis client returning None (cache miss)
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)
            service.redis_client = mock_redis
            
            result = await service.get("nonexistent-key")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_set_with_mock_redis(self):
        """Test cache set with mocked Redis."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_ttl_seconds = 3600
            
            service = CacheService()
            
            # Mock Redis client
            mock_redis = AsyncMock()
            mock_redis.setex = AsyncMock(return_value=True)
            service.redis_client = mock_redis
            
            test_data = {"message": "test"}
            result = await service.set("test-key", test_data, ttl=600)
            
            assert result is True
            mock_redis.setex.assert_called_once_with(
                "test-key",
                600,
                json.dumps(test_data)
            )
    
    @pytest.mark.asyncio
    async def test_delete_with_mock_redis(self):
        """Test cache delete with mocked Redis."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_ttl_seconds = 3600
            
            service = CacheService()
            
            # Mock Redis client
            mock_redis = AsyncMock()
            mock_redis.delete = AsyncMock(return_value=1)
            service.redis_client = mock_redis
            
            result = await service.delete("test-key")
            
            assert result is True
            mock_redis.delete.assert_called_once_with("test-key")
    
    @pytest.mark.asyncio
    async def test_get_handles_redis_error(self):
        """Test that get handles Redis errors gracefully."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_ttl_seconds = 3600
            
            service = CacheService()
            
            # Mock Redis client that raises an exception
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(side_effect=Exception("Redis connection error"))
            service.redis_client = mock_redis
            
            result = await service.get("test-key")
            
            # Should return None on error, not raise
            assert result is None


class TestCacheServiceSingleton:
    """Tests for cache service singleton pattern."""
    
    def test_get_cache_service_returns_none_when_disabled(self):
        """Test that get_cache_service returns None when caching is disabled."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = False
            
            # Reset the singleton
            import app.services.cache_service as cache_module
            cache_module._cache_service = None
            
            result = get_cache_service()
            
            assert result is None
    
    def test_get_cache_service_returns_singleton(self):
        """Test that get_cache_service returns the same instance."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_ttl_seconds = 3600
            
            # Reset the singleton
            import app.services.cache_service as cache_module
            cache_module._cache_service = None
            
            service1 = get_cache_service()
            service2 = get_cache_service()
            
            assert service1 is service2
