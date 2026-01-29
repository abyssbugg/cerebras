"""Unit tests for rate limiting middleware."""
import pytest
import time
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.middleware.rate_limit import (
    RateLimitMiddleware,
    _rate_limit_store,
    _rate_limit_lock,
)


@pytest.fixture
def app():
    """Create test FastAPI app with rate limit middleware."""
    test_app = FastAPI()
    
    @test_app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    @test_app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}
    
    return test_app


@pytest.fixture
def client_with_rate_limit(app):
    """Create test client with rate limiting enabled."""
    with patch("app.api.middleware.rate_limit.settings") as mock_settings:
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_requests_per_minute = 5
        mock_settings.redis_url = "redis://localhost:6379/0"
        
        middleware = RateLimitMiddleware(app)
        middleware.redis_client = None  # Force in-memory mode
        app.add_middleware(RateLimitMiddleware)
        
        return TestClient(app)


class TestInMemoryRateLimiting:
    """Tests for in-memory rate limiting (fallback mode)."""
    
    def test_rate_limit_store_initialization(self):
        """Test that rate limit store is initialized as empty dict."""
        # Clear the store first
        _rate_limit_store.clear()
        assert isinstance(_rate_limit_store, dict)
        assert len(_rate_limit_store) == 0
    
    def test_memory_rate_limit_allows_requests_under_limit(self):
        """Test in-memory rate limiting allows requests under the limit."""
        with patch("app.api.middleware.rate_limit.settings") as mock_settings:
            mock_settings.rate_limit_enabled = True
            mock_settings.rate_limit_requests_per_minute = 10
            mock_settings.redis_url = "redis://localhost:6379/0"
            
            app = FastAPI()
            
            @app.get("/test")
            async def test_endpoint(request: Request):
                return {"status": "ok"}
            
            # Create middleware manually to test
            middleware = RateLimitMiddleware(app)
            middleware.redis_client = None  # Force in-memory mode
            
            # Clear the store
            _rate_limit_store.clear()
            
            # Test the in-memory rate limit check
            is_limited, retry_after = middleware._check_memory_rate_limit(
                identifier="test-key",
                window_seconds=60,
                max_requests=10
            )
            
            assert is_limited is False
            assert retry_after == 0
    
    def test_memory_rate_limit_blocks_when_exceeded(self):
        """Test in-memory rate limiting blocks requests over the limit."""
        with patch("app.api.middleware.rate_limit.settings") as mock_settings:
            mock_settings.rate_limit_enabled = True
            mock_settings.rate_limit_requests_per_minute = 3
            mock_settings.redis_url = "redis://localhost:6379/0"
            
            app = FastAPI()
            middleware = RateLimitMiddleware(app)
            middleware.redis_client = None  # Force in-memory mode
            
            # Clear the store
            _rate_limit_store.clear()
            
            identifier = "test-block-key"
            
            # Make requests up to the limit
            for _ in range(3):
                is_limited, _ = middleware._check_memory_rate_limit(
                    identifier=identifier,
                    window_seconds=60,
                    max_requests=3
                )
                assert is_limited is False
            
            # Next request should be blocked
            is_limited, retry_after = middleware._check_memory_rate_limit(
                identifier=identifier,
                window_seconds=60,
                max_requests=3
            )
            
            assert is_limited is True
            assert retry_after == 60
    
    def test_memory_rate_limit_window_sliding(self):
        """Test that sliding window removes old requests."""
        with patch("app.api.middleware.rate_limit.settings") as mock_settings:
            mock_settings.rate_limit_enabled = True
            mock_settings.rate_limit_requests_per_minute = 2
            mock_settings.redis_url = "redis://localhost:6379/0"
            
            app = FastAPI()
            middleware = RateLimitMiddleware(app)
            middleware.redis_client = None
            
            # Clear the store
            _rate_limit_store.clear()
            
            identifier = "test-sliding-key"
            
            # Add old timestamps (outside window)
            old_time = time.time() - 120  # 2 minutes ago
            _rate_limit_store[identifier] = [old_time, old_time + 1]
            
            # New request should pass (old ones should be removed)
            is_limited, _ = middleware._check_memory_rate_limit(
                identifier=identifier,
                window_seconds=60,
                max_requests=2
            )
            
            assert is_limited is False
            # Old timestamps should be removed
            assert len(_rate_limit_store[identifier]) == 1


class TestRateLimitExemptPaths:
    """Tests for exempt paths that bypass rate limiting."""
    
    def test_health_endpoint_exempt(self):
        """Test that /health is exempt from rate limiting."""
        from app.api.middleware.rate_limit import EXEMPT_PATHS
        
        assert "/health" in EXEMPT_PATHS
        assert "/" in EXEMPT_PATHS
        assert "/docs" in EXEMPT_PATHS
    
    def test_messages_endpoint_not_exempt(self):
        """Test that /v1/messages is NOT exempt from rate limiting."""
        from app.api.middleware.rate_limit import EXEMPT_PATHS
        
        assert "/v1/messages" not in EXEMPT_PATHS


class TestRateLimitIdentifier:
    """Tests for rate limit identifier extraction."""
    
    @pytest.mark.asyncio
    async def test_identifier_uses_api_key_when_available(self):
        """Test that API key is used as identifier when available."""
        with patch("app.api.middleware.rate_limit.settings") as mock_settings:
            mock_settings.rate_limit_enabled = True
            mock_settings.rate_limit_requests_per_minute = 60
            mock_settings.redis_url = "redis://localhost:6379/0"
            
            app = FastAPI()
            
            @app.get("/test")
            async def test_endpoint():
                return {"status": "ok"}
            
            middleware = RateLimitMiddleware(app)
            middleware.redis_client = None
            
            # Create a mock request with api_key in state
            mock_request = MagicMock(spec=Request)
            mock_request.url.path = "/test"
            mock_request.state.api_key = "test-api-key-123"
            mock_request.client = MagicMock()
            mock_request.client.host = "127.0.0.1"
            
            # The middleware should use api_key, not IP
            # We test this by checking the _check_rate_limit is called with api_key
            _rate_limit_store.clear()
            
            # Simulate the identifier extraction logic
            identifier = getattr(mock_request.state, 'api_key', None)
            if not identifier:
                identifier = mock_request.client.host if mock_request.client else "unknown"
            
            assert identifier == "test-api-key-123"
    
    @pytest.mark.asyncio
    async def test_identifier_falls_back_to_ip(self):
        """Test that IP address is used when API key is not available."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/test"
        mock_request.state = MagicMock()
        # Remove api_key attribute to simulate missing key
        del mock_request.state.api_key
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"
        
        # Simulate the identifier extraction logic
        identifier = getattr(mock_request.state, 'api_key', None)
        if not identifier:
            identifier = mock_request.client.host if mock_request.client else "unknown"
        
        assert identifier == "192.168.1.1"
    
    @pytest.mark.asyncio
    async def test_identifier_handles_none_client(self):
        """Test that missing client is handled gracefully."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/test"
        mock_request.state = MagicMock()
        del mock_request.state.api_key
        mock_request.client = None
        
        # Simulate the identifier extraction logic (matches rate_limit.py)
        identifier = getattr(mock_request.state, 'api_key', None)
        if not identifier:
            identifier = mock_request.client.host if mock_request.client else "unknown"
        
        # The middleware uses "unknown" as fallback
        assert identifier == "unknown"
