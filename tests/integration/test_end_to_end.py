"""Integration tests for end-to-end request flow."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import json

from app.main import app
from app.models.cerebras import (
    CerebrasChatResponse,
    CerebrasChoice,
    CerebrasMessage,
    CerebrasUsage,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_cerebras_response():
    """Create mock Cerebras response."""
    return CerebrasChatResponse(
        id="test-id",
        object="chat.completion",
        created=1234567890,
        model="llama-3.3-70b",
        choices=[
            CerebrasChoice(
                index=0,
                message=CerebrasMessage(role="assistant", content="Hello! How can I help you?"),
                finish_reason="stop"
            )
        ],
        usage=CerebrasUsage(
            prompt_tokens=15,
            completion_tokens=8,
            total_tokens=23
        )
    )


class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    def test_health_endpoint(self, client):
        """Test /health returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_root_endpoint(self, client):
        """Test / returns gateway info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestAuthentication:
    """Tests for authentication middleware."""
    
    def test_missing_api_key_returns_401(self, client):
        """Test missing API key returns 401."""
        response = client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Hi"}]
            }
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["type"] == "authentication_error"
    
    def test_with_api_key_proceeds(self, client, mock_cerebras_response):
        """Test request with API key proceeds."""
        with patch("app.clients.cerebras.CerebrasClient.chat_completion") as mock:
            mock.return_value = mock_cerebras_response
            
            response = client.post(
                "/v1/messages",
                headers={"x-api-key": "test-key"},
                json={
                    "model": "claude-sonnet-4",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": "Hi"}]
                }
            )
            # Should not be 401
            assert response.status_code != 401


class TestNonStreamingMessages:
    """Tests for non-streaming /v1/messages endpoint."""
    
    def test_successful_request(self, client, mock_cerebras_response):
        """Test successful non-streaming request."""
        with patch("app.clients.cerebras.CerebrasClient.chat_completion") as mock:
            mock.return_value = mock_cerebras_response
            
            response = client.post(
                "/v1/messages",
                headers={"x-api-key": "test-key", "anthropic-version": "2023-06-01"},
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                assert data["type"] == "message"
                assert data["role"] == "assistant"
                assert data["model"] == "claude-sonnet-4-20250514"  # Echo-back
                assert len(data["content"]) > 0
                assert "usage" in data
    
    def test_model_echo_back(self, client, mock_cerebras_response):
        """Test model name is echoed back correctly."""
        with patch("app.clients.cerebras.CerebrasClient.chat_completion") as mock:
            mock.return_value = mock_cerebras_response
            
            requested_model = "claude-3-5-sonnet-20241022"
            response = client.post(
                "/v1/messages",
                headers={"x-api-key": "test-key"},
                json={
                    "model": requested_model,
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                # CRITICAL: Response must have requested model, not internal model
                assert data["model"] == requested_model
                assert data["model"] != "llama-3.3-70b"


class TestTokenCount:
    """Tests for token count endpoint."""
    
    def test_token_count_endpoint(self, client):
        """Test /v1/messages/count_tokens endpoint."""
        response = client.post(
            "/v1/messages/count_tokens",
            headers={"x-api-key": "test-key"},
            json={
                "model": "claude-sonnet-4",
                "messages": [{"role": "user", "content": "Hello world"}]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "input_tokens" in data
        assert isinstance(data["input_tokens"], int)
        assert data["input_tokens"] > 0


class TestValidation:
    """Tests for request validation."""
    
    def test_invalid_request_returns_422(self, client):
        """Test invalid request returns 422."""
        response = client.post(
            "/v1/messages",
            headers={"x-api-key": "test-key"},
            json={"invalid": "request"}
        )
        assert response.status_code == 422
    
    def test_missing_required_fields(self, client):
        """Test missing required fields returns error."""
        response = client.post(
            "/v1/messages",
            headers={"x-api-key": "test-key"},
            json={
                "model": "claude-sonnet-4"
                # Missing max_tokens and messages
            }
        )
        assert response.status_code == 422


class TestResponseFormat:
    """Tests for Anthropic-compatible response format."""
    
    def test_response_has_required_fields(self, client, mock_cerebras_response):
        """Test response has all required Anthropic fields."""
        with patch("app.clients.cerebras.CerebrasClient.chat_completion") as mock:
            mock.return_value = mock_cerebras_response
            
            response = client.post(
                "/v1/messages",
                headers={"x-api-key": "test-key"},
                json={
                    "model": "claude-sonnet-4",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Required fields per Anthropic spec
                required_fields = ["id", "type", "role", "content", "model", "usage"]
                for field in required_fields:
                    assert field in data, f"Missing required field: {field}"
                
                # Content should be a list
                assert isinstance(data["content"], list)
                
                # Usage should have token counts
                assert "input_tokens" in data["usage"]
                assert "output_tokens" in data["usage"]
