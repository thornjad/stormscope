"""async in-memory TTL cache with stale-data fallback."""

import asyncio
import time


class TTLCache:
    def __init__(self):
        self._store: dict[str, tuple[float, object]] = {}
        self._lock = asyncio.Lock()

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
            self._store[key] = (time.monotonic() + ttl_seconds, value)

    async def invalidate(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
