"""Tests for async TTL cache."""

import asyncio
import time

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
