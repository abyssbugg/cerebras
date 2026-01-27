from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # Cerebras API
    cerebras_api_key: str = ""
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    cerebras_model: str = "llama-3.3-70b"

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

    # Prompt Tuning
    temperature_multiplier_code: float = 0.85
    heartbeat_interval_seconds: int = 15

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
