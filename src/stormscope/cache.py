"""async in-memory TTL cache with stale-data fallback."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class TTLCache:
    def __init__(self, max_size: int = 256):
        self._store: dict[str, tuple[float, object]] = {}
        self._lock = asyncio.Lock()
        self._max_size = max_size

    async def get(self, key: str) -> tuple[object | None, bool]:
        """Return (value, is_stale). Expired entries kept for fallback."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None, False
            expires_at, value = entry
            if time.monotonic() > expires_at:
                return value, True
            return value, False

    async def set(self, key: str, value: object, ttl_seconds: float) -> None:
        async with self._lock:
            if key not in self._store and len(self._store) >= self._max_size:
                stalest_key = min(self._store, key=lambda k: self._store[k][0])
                del self._store[stalest_key]
            self._store[key] = (time.monotonic() + ttl_seconds, value)

    async def invalidate(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    async def get_or_fetch(
        self, key: str, ttl: float, fetcher: Callable[[], Awaitable[T]],
    ) -> T:
        """Return cached value if fresh, otherwise fetch, cache, and return.

        On fetch failure, returns stale data if available, otherwise re-raises.
        """
        cached, is_stale = await self.get(key)
        if cached is not None and not is_stale:
            return cached
        try:
            value = await fetcher()
            await self.set(key, value, ttl)
            return value
        except Exception:
            if cached is not None:
                return cached
            raise
