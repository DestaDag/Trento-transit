import asyncio

import httpx
import pytest

from app.services.cache import SingleFlightCache


@pytest.mark.asyncio
async def test_single_flight_only_fetches_once():
    cache = SingleFlightCache(ttl_seconds=30)
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {"trips": [1]}

    results = await asyncio.gather(
        *(cache.get_or_fetch("100:U", fetch) for _ in range(20))
    )
    assert calls == 1
    assert all(result == {"trips": [1]} for result in results)


@pytest.mark.asyncio
async def test_stale_fallback_after_http_error():
    cache = SingleFlightCache(ttl_seconds=30)
    stale = {"trips": ["cached"]}

    async def fetch():
        request = httpx.Request("GET", "https://example.test")
        raise httpx.HTTPStatusError(
            "503", request=request, response=httpx.Response(503, request=request)
        )

    result = await cache.get_or_fetch("stop", fetch, lambda: stale)
    assert result == stale