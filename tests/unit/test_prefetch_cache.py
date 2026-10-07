import asyncio
import pytest
from app.rag.prefetch import SpeculativePrefetchCache


@pytest.mark.asyncio
async def test_prefetch_cache_hit_and_miss():
    cache = SpeculativePrefetchCache(ttl_seconds=1.0)

    # Initially miss
    assert await cache.get("infinity pool hours") is None

    # Set cache
    docs = [{"content": "Pool is open from 6am to 10pm.", "source": "amenities"}]
    await cache.set("infinity pool hours", docs)

    # Exact query hit
    hit = await cache.get("infinity pool hours")
    assert hit is not None
    assert hit[0]["content"] == docs[0]["content"]

    # Normalized / token overlap hit
    overlap_hit = await cache.get("what are the pool hours?")
    assert overlap_hit is not None


@pytest.mark.asyncio
async def test_prefetch_cache_expiration():
    cache = SpeculativePrefetchCache(ttl_seconds=0.1)
    await cache.set("checkout time", [{"content": "11 AM"}])

    # Immediate check
    assert await cache.get("checkout time") is not None

    # Wait for TTL to elapse
    await asyncio.sleep(0.15)
    assert await cache.get("checkout time") is None
