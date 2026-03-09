"""Tests for async TTL cache."""

import asyncio
import time

import pytest

from stormscope.cache import TTLCache


async def test_set_and_get():
    cache = TTLCache()
    await cache.set("key", "value", ttl_seconds=60)
    value, is_stale = await cache.get("key")
    assert value == "value"
    assert is_stale is False


async def test_missing_key_returns_none():
    cache = TTLCache()
    value, is_stale = await cache.get("missing")
    assert value is None
    assert is_stale is False


async def test_stale_after_ttl():
    cache = TTLCache()
    await cache.set("key", "value", ttl_seconds=0.01)
    await asyncio.sleep(0.02)
    value, is_stale = await cache.get("key")
    assert value == "value"
    assert is_stale is True


async def test_clear():
    cache = TTLCache()
    await cache.set("a", 1, ttl_seconds=60)
    await cache.set("b", 2, ttl_seconds=60)
    await cache.clear()
    val_a, _ = await cache.get("a")
    val_b, _ = await cache.get("b")
    assert val_a is None
    assert val_b is None


async def test_overwrite():
    cache = TTLCache()
    await cache.set("key", "old", ttl_seconds=60)
    await cache.set("key", "new", ttl_seconds=60)
    value, is_stale = await cache.get("key")
    assert value == "new"
    assert is_stale is False


async def test_invalidate():
    cache = TTLCache()
    await cache.set("key", "value", ttl_seconds=60)
    await cache.invalidate("key")
    value, _ = await cache.get("key")
    assert value is None


async def test_invalidate_missing_key():
    cache = TTLCache()
    await cache.invalidate("nonexistent")


async def test_max_size_eviction():
    cache = TTLCache(max_size=2)
    await cache.set("a", 1, ttl_seconds=60)
    await cache.set("b", 2, ttl_seconds=60)
    await cache.set("c", 3, ttl_seconds=60)
    val_a, _ = await cache.get("a")
    assert val_a is None
    val_b, _ = await cache.get("b")
    assert val_b == 2
    val_c, _ = await cache.get("c")
    assert val_c == 3


async def test_max_size_evicts_stalest():
    cache = TTLCache(max_size=2)
    await cache.set("a", 1, ttl_seconds=10)
    await cache.set("b", 2, ttl_seconds=60)
    # "a" expires sooner so it's the stalest
    await cache.set("c", 3, ttl_seconds=60)
    val_a, _ = await cache.get("a")
    assert val_a is None
    val_b, _ = await cache.get("b")
    assert val_b == 2


async def test_get_or_fetch_fresh():
    cache = TTLCache()
    result = await cache.get_or_fetch("k", 60, fetcher=lambda: _async_val("hello"))
    assert result == "hello"
    cached, stale = await cache.get("k")
    assert cached == "hello"
    assert stale is False


async def test_get_or_fetch_cached():
    cache = TTLCache()
    await cache.set("k", "cached", 60)
    calls = []

    async def _fetcher():
        calls.append(1)
        return "new"

    result = await cache.get_or_fetch("k", 60, fetcher=_fetcher)
    assert result == "cached"
    assert calls == []


async def test_get_or_fetch_stale_fallback():
    cache = TTLCache()
    await cache.set("k", "stale_val", 0.01)
    await asyncio.sleep(0.02)

    async def _failing():
        raise RuntimeError("down")

    result = await cache.get_or_fetch("k", 60, fetcher=_failing)
    assert result == "stale_val"


async def test_get_or_fetch_miss_and_failure():
    cache = TTLCache()

    async def _failing():
        raise RuntimeError("down")

    with pytest.raises(RuntimeError, match="down"):
        await cache.get_or_fetch("k", 60, fetcher=_failing)


async def _async_val(v):
    return v
