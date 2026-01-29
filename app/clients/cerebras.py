import json
import asyncio
from typing import AsyncIterator, Optional
import httpx
from app.models.cerebras import (
    CerebrasChatRequest,
    CerebrasChatResponse,
    CerebrasStreamChunk,
)
from app.models.errors import APIError, RateLimitError, OverloadedError
from app.config import get_settings
from app.utils.logging import get_logger
from app.utils.metrics import UPSTREAM_LATENCY

settings = get_settings()
logger = get_logger(__name__)


class CerebrasClient:
    """
    Cerebras API client supporting both:
    - Static API key (set in constructor or from settings)
    - Per-request API key (for passthrough mode, like GLM/MiniMax)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        connect_timeout: Optional[float] = None,
        max_retries: Optional[int] = None
    ):
        self.default_api_key = api_key or settings.cerebras_api_key
        self.base_url = (base_url or settings.cerebras_base_url).rstrip("/")
        self.timeout = timeout or settings.cerebras_timeout_seconds
        self.connect_timeout = connect_timeout or settings.cerebras_connect_timeout_seconds
        self.max_retries = max_retries if max_retries is not None else settings.cerebras_max_retries
        
        # Create client without Authorization header (we'll add it per-request)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(self.timeout, connect=self.connect_timeout),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
    
    def _get_headers(self, api_key: Optional[str] = None) -> dict:
        """Get headers with the appropriate API key."""
        key = api_key or self.default_api_key
        if not key:
            raise APIError("No API key provided", 401)
        return {"Authorization": f"Bearer {key}"}

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        api_key: Optional[str] = None,
        **kwargs
    ) -> httpx.Response:
        """Execute request with exponential backoff retry."""
        last_exception = None
        headers = self._get_headers(api_key)
        
        # Merge headers with any existing headers in kwargs
        if "headers" in kwargs:
            kwargs["headers"].update(headers)
        else:
            kwargs["headers"] = headers
        
        for attempt in range(self.max_retries):
            try:
                response = await self._client.request(method, url, **kwargs)
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get("retry-after", 2 ** attempt))
                    logger.warning(
                        "Rate limited by Cerebras",
                        attempt=attempt,
                        retry_after=retry_after
                    )
                    await asyncio.sleep(retry_after)
                    continue
                
                if response.status_code >= 500:
                    logger.warning(
                        "Cerebras server error",
                        status_code=response.status_code,
                        attempt=attempt
                    )
                    await asyncio.sleep(2 ** attempt)
                    continue
                
                return response
                
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                last_exception = e
                logger.warning(
                    "Cerebras connection error",
                    error=str(e),
                    attempt=attempt
                )
                await asyncio.sleep(2 ** attempt)
                continue
        
        if last_exception:
            raise APIError(f"Failed after {self.max_retries} retries: {last_exception}")
        raise APIError("Request failed with unknown error")

    async def chat_completion(
        self,
        request: CerebrasChatRequest,
        api_key: Optional[str] = None
    ) -> CerebrasChatResponse:
        """
        Non-streaming chat completion.
        
        Args:
            request: The Cerebras chat request
            api_key: Optional API key to use (for passthrough mode).
                     If not provided, uses the default key.
        """
        request_data = request.model_dump(exclude_none=True)
        request_data["stream"] = False
        
        # Track upstream latency
        import time
        upstream_start = time.time()
        
        response = await self._request_with_retry(
            "POST",
            "/chat/completions",
            api_key=api_key,
            json=request_data
        )
        
        # Record upstream latency
        upstream_latency = time.time() - upstream_start
        UPSTREAM_LATENCY.observe(upstream_latency)
        
        if response.status_code == 429:
            raise RateLimitError("Cerebras rate limit exceeded")
        
        if response.status_code == 401:
            raise APIError("Invalid Cerebras API key", 401)
        
        if response.status_code >= 500:
            raise OverloadedError("Cerebras service unavailable")
        
        if response.status_code != 200:
            error_detail = response.text
            logger.error(
                "Cerebras API error",
                status_code=response.status_code,
                error=error_detail
            )
            raise APIError(f"Cerebras API error: {error_detail}", response.status_code)
        
        return CerebrasChatResponse(**response.json())

    async def chat_completion_stream(
        self,
        request: CerebrasChatRequest,
        api_key: Optional[str] = None
    ) -> AsyncIterator[CerebrasStreamChunk]:
        """
        Streaming chat completion.
        
        Args:
            request: The Cerebras chat request
            api_key: Optional API key to use (for passthrough mode).
                     If not provided, uses the default key.
        """
        request_data = request.model_dump(exclude_none=True)
        request_data["stream"] = True
        
        headers = self._get_headers(api_key)
        
        async with self._client.stream(
            "POST",
            "/chat/completions",
            json=request_data,
            headers=headers
        ) as response:
            if response.status_code == 429:
                raise RateLimitError("Cerebras rate limit exceeded")
            
            if response.status_code == 401:
                raise APIError("Invalid Cerebras API key", 401)
            
            if response.status_code >= 500:
                raise OverloadedError("Cerebras service unavailable")
            
            if response.status_code != 200:
                error_text = await response.aread()
                logger.error(
                    "Cerebras API error",
                    status_code=response.status_code,
                    error=error_text.decode()
                )
                raise APIError(
                    f"Cerebras API error: {error_text.decode()}",
                    response.status_code
                )
            
            async for line in response.aiter_lines():
                if not line or line.startswith(":"):
                    continue
                
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    
                    try:
                        chunk_data = json.loads(data)
                        yield CerebrasStreamChunk(**chunk_data)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "Failed to parse Cerebras stream chunk",
                            error=str(e),
                            data=data
                        )
                        continue


_client: Optional[CerebrasClient] = None


def get_cerebras_client() -> CerebrasClient:
    global _client
    if _client is None:
        _client = CerebrasClient()
    return _client
