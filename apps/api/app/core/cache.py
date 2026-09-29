"""Small JSON cache used for search results and fetched pages.

Redis is optional: when ``REDIS_URL`` is empty (or Redis is unreachable) an
in-process TTL cache is used instead, so the app runs without extra services.
The cache is strictly best-effort and never raises.
"""

import json
import logging
import time
from collections import OrderedDict
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class MemoryCache:
    backend = "memory"

    def __init__(self, max_entries: int = 2048):
        self._data: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._max_entries = max_entries

    async def get_json(self, key: str) -> Optional[Any]:
        item = self._data.get(key)
        if item is None:
            return None
        expires_at, raw = item
        if expires_at < time.monotonic():
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl: int) -> None:
        self._data[key] = (time.monotonic() + ttl, json.dumps(value))
        self._data.move_to_end(key)
        while len(self._data) > self._max_entries:
            self._data.popitem(last=False)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._data.clear()


class RedisCache:
    backend = "redis"

    def __init__(self, url: str):
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(url, encoding="utf-8", decode_responses=True, socket_timeout=2)
        self._warned = False

    def _warn(self, exc: Exception) -> None:
        if not self._warned:
            logger.warning("Redis cache unavailable, continuing without cache: %s", exc)
            self._warned = True

    async def get_json(self, key: str) -> Optional[Any]:
        try:
            raw = await self._client.get(key)
        except Exception as exc:  # noqa: BLE001 - cache must never break a research
            self._warn(exc)
            return None
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: Any, ttl: int) -> None:
        try:
            await self._client.set(key, json.dumps(value), ex=ttl)
        except Exception as exc:  # noqa: BLE001
            self._warn(exc)

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:  # noqa: BLE001
            return False

    async def close(self) -> None:
        await self._client.aclose()


_cache: Optional[MemoryCache | RedisCache] = None


def get_cache() -> MemoryCache | RedisCache:
    global _cache
    if _cache is None:
        _cache = RedisCache(settings.REDIS_URL) if settings.REDIS_URL else MemoryCache()
    return _cache


async def close_cache() -> None:
    global _cache
    if _cache is not None:
        await _cache.close()
        _cache = None
