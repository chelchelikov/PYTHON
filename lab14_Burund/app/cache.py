"""Асинхронный кэш на Redis (redis.asyncio)."""

import json
import logging
from typing import Any, Protocol

log = logging.getLogger("hotel.cache")


class Cache(Protocol):
    async def get(self, key: str) -> Any | None: ...

    async def set(self, key: str, value: Any, ttl: int) -> None: ...

    async def delete(self, *keys: str) -> None: ...


class RedisCache:
    def __init__(self, client, prefix: str = "lab14:") -> None:
        self.client = client
        self.prefix = prefix

    async def get(self, key: str) -> Any | None:
        try:
            raw = await self.client.get(self.prefix + key)
        except Exception as error:  # Redis недоступен — работаем без кэша
            log.warning("Redis GET failed: %s", error)
            return None
        return None if raw is None else json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            await self.client.set(self.prefix + key, json.dumps(value, ensure_ascii=False), ex=ttl)
        except Exception as error:
            log.warning("Redis SET failed: %s", error)

    async def delete(self, *keys: str) -> None:
        try:
            await self.client.delete(*(self.prefix + k for k in keys))
        except Exception as error:
            log.warning("Redis DELETE failed: %s", error)


class NullCache:
    """Используется, если Redis не настроен: всегда промах."""

    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        return None

    async def delete(self, *keys: str) -> None:
        return None


def create_cache(redis_url: str | None) -> Cache:
    if not redis_url:
        return NullCache()
    from redis import asyncio as aioredis

    return RedisCache(aioredis.from_url(redis_url, decode_responses=True,
                                        socket_connect_timeout=1))
