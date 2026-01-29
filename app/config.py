from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # Cerebras API
    cerebras_api_key: str = ""
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    cerebras_model: str = "zai-glm-4.7"
    
    # Connection Settings
    cerebras_timeout_seconds: float = 120.0  # Total request timeout
    cerebras_connect_timeout_seconds: float = 10.0  # Connection timeout
    cerebras_max_retries: int = 3  # Max retry attempts

    # Gateway Config
    environment: str = "development"
    debug: bool = False
    api_key_header: str = "x-api-key"
    gateway_api_keys: str = ""  # Comma-separated list of valid API keys

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    redis_url: str = "redis://localhost:6379/0"

    # Caching
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600

    # Optional Features
    enable_fallback_providers: bool = False
    groq_api_key: Optional[str] = None
    together_api_key: Optional[str] = None

    # Observability
    sentry_dsn: Optional[str] = None
    otel_service_name: str = "cerebras-anthropic-gateway"
    otel_exporter_endpoint: Optional[str] = None

    # Server Config
    host: str = "0.0.0.0"
    port: int = 8080
    
    # CORS Configuration
    # Comma-separated list of allowed origins. Use "*" for development only.
    # Example: "https://cursor.so,https://claude.ai,https://your-domain.com"
    cors_origins: str = "*"

    # Prompt Tuning
    temperature_multiplier_code: float = 0.85
    heartbeat_interval_seconds: int = 15
    
    # Context Length Management
    # Cerebras zai-glm-4.7 has 128K token limit (~131,072 tokens)
    # Claude has 200K - so we need to manage context to avoid errors
    context_limit_tokens: int = 120000  # Leave buffer below 128K
    max_tool_result_chars: int = 50000  # Max chars per tool result (0 = no limit)
    truncation_enabled: bool = True  # Enable automatic truncation
    truncation_strategy: str = "truncate"  # "truncate", "error", or "warn"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
