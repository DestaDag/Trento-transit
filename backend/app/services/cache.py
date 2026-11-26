import asyncio
import time
from collections.abc import Awaitable, Callable, Hashable
from typing import TypeVar

import httpx
from cachetools import TTLCache

T = TypeVar("T")


class SingleFlightCache[T]:
    def __init__(self, ttl_seconds: float = 30.0, maxsize: int = 512) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: TTLCache[Hashable, tuple[float, T]] = TTLCache(
            maxsize=maxsize, ttl=ttl_seconds
        )
        self._locks: dict[Hashable, asyncio.Lock] = {}

    def get(self, key: Hashable) -> T | None:
        entry = self._cache.get(key)
        return entry[1] if entry else None

    def put(self, key: Hashable, value: T) -> None:
        self._cache[key] = (time.monotonic(), value)

    def invalidate(self, key: Hashable) -> None:
        self._cache.pop(key, None)

    def _lock_for(self, key: Hashable) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def get_or_fetch(
        self,
        key: Hashable,
        fetch: Callable[[], Awaitable[T]],
        stale_fallback: Callable[[], T | None] | None = None,
    ) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached

        lock = self._lock_for(key)
        async with lock:
            cached = self.get(key)
            if cached is not None:
                return cached
            try:
                value = await fetch()
            except (TimeoutError, httpx.HTTPError, ValueError):
                fallback = stale_fallback() if stale_fallback else None
                if fallback is not None:
                    return fallback
                raise
            self.put(key, value)
            return value
