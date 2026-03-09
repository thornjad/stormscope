"""shared base for async API clients with lazy httpx client and caching."""

import asyncio

import httpx

from stormscope.cache import TTLCache


class BaseAPIClient:
    def __init__(self, *, headers: dict[str, str], timeout: float = 30.0, base_url: str = "", **client_kwargs):
        self._cache = TTLCache()
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()
        self._client_headers = headers
        self._client_timeout = timeout
        self._client_base_url = base_url
        self._client_kwargs = client_kwargs

    async def _get_client(self) -> httpx.AsyncClient:
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    headers=self._client_headers,
                    timeout=self._client_timeout,
                    **({"base_url": self._client_base_url} if self._client_base_url else {}),
                    **self._client_kwargs,
                )
            return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
