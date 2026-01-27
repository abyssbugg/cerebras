"""
Fallback Provider Service - OPTIONAL FEATURE (not currently wired)

This service provides multi-provider fallback when Cerebras is unavailable.
To enable: Set ENABLE_FALLBACK_PROVIDERS=true in environment.

TODO: Wire into messages.py create_message() when ENABLE_FALLBACK_PROVIDERS is true.
"""
from typing import Optional, List, AsyncIterator
import httpx
from app.models.cerebras import CerebrasChatRequest, CerebrasChatResponse, CerebrasStreamChunk
from app.config import get_settings
from app.utils.logging import get_logger
from app.utils.metrics import ERROR_COUNT

settings = get_settings()
logger = get_logger(__name__)


class FallbackProvider:
    def __init__(self, name: str, api_key: str, base_url: str, model: str):
        self.name = name
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = None
    
    def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class FallbackService:
    """
    Multi-provider fallback chain for graceful degradation.
    Fallback order: Cerebras -> Groq -> Together AI
    Feature-flagged, disabled by default.
    """
    
    def __init__(self):
        self.providers: List[FallbackProvider] = []
        self._init_providers()
    
    def _init_providers(self):
        """Initialize fallback providers if configured."""
        if not settings.enable_fallback_providers:
            logger.info("Fallback providers disabled")
            return
        
        # Groq fallback
        if settings.groq_api_key:
            self.providers.append(FallbackProvider(
                name="groq",
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
                model="llama-3.3-70b-versatile"
            ))
            logger.info("Groq fallback provider configured")
        
        # Together AI fallback
        if settings.together_api_key:
            self.providers.append(FallbackProvider(
                name="together",
                api_key=settings.together_api_key,
                base_url="https://api.together.xyz/v1",
                model="meta-llama/Llama-3.3-70B-Instruct-Turbo"
            ))
            logger.info("Together AI fallback provider configured")
    
    async def chat_completion_with_fallback(
        self,
        request: CerebrasChatRequest,
        primary_error: Exception
    ) -> Optional[CerebrasChatResponse]:
        """
        Attempt chat completion using fallback providers.
        Returns None if all providers fail.
        """
        if not self.providers:
            return None
        
        logger.warning(
            "Primary provider failed, attempting fallback",
            primary_error=str(primary_error)
        )
        
        for provider in self.providers:
            try:
                logger.info(f"Trying fallback provider: {provider.name}")
                
                # Adapt request for provider
                request_data = request.model_dump(exclude_none=True)
                request_data["model"] = provider.model
                request_data["stream"] = False
                
                client = provider.get_client()
                response = await client.post(
                    "/chat/completions",
                    json=request_data
                )
                
                if response.status_code == 200:
                    logger.info(f"Fallback to {provider.name} successful")
                    return CerebrasChatResponse(**response.json())
                else:
                    logger.warning(
                        f"Fallback provider {provider.name} failed",
                        status_code=response.status_code
                    )
                    ERROR_COUNT.labels(error_type=f"fallback_{provider.name}_error").inc()
                    
            except Exception as e:
                logger.warning(
                    f"Fallback provider {provider.name} error",
                    error=str(e)
                )
                ERROR_COUNT.labels(error_type=f"fallback_{provider.name}_error").inc()
                continue
        
        return None
    
    async def close(self):
        """Close all provider connections."""
        for provider in self.providers:
            await provider.close()


_fallback_service: Optional[FallbackService] = None


def get_fallback_service() -> Optional[FallbackService]:
    """Get fallback service singleton."""
    global _fallback_service
    
    if not settings.enable_fallback_providers:
        return None
    
    if _fallback_service is None:
        _fallback_service = FallbackService()
    
    return _fallback_service
