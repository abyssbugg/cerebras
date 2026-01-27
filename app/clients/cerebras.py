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

settings = get_settings()
logger = get_logger(__name__)


class CerebrasClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 120.0,
        max_retries: int = 3
    ):
        self.api_key = api_key or settings.cerebras_api_key
        self.base_url = (base_url or settings.cerebras_base_url).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )

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
        **kwargs
    ) -> httpx.Response:
        """Execute request with exponential backoff retry."""
        last_exception = None
        
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
        request: CerebrasChatRequest
    ) -> CerebrasChatResponse:
        """Non-streaming chat completion."""
        request_data = request.model_dump(exclude_none=True)
        request_data["stream"] = False
        
        response = await self._request_with_retry(
            "POST",
            "/chat/completions",
            json=request_data
        )
        
        if response.status_code == 429:
            raise RateLimitError("Cerebras rate limit exceeded")
        
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
        request: CerebrasChatRequest
    ) -> AsyncIterator[CerebrasStreamChunk]:
        """Streaming chat completion."""
        request_data = request.model_dump(exclude_none=True)
        request_data["stream"] = True
        
        async with self._client.stream(
            "POST",
            "/chat/completions",
            json=request_data
        ) as response:
            if response.status_code == 429:
                raise RateLimitError("Cerebras rate limit exceeded")
            
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
