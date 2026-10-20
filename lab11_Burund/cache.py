"""Кэш: Redis (основной вариант) или память процесса (если Redis недоступен)."""

import json
import time
from typing import Any, Protocol


class Cache(Protocol):
    name: str

    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl: int) -> None: ...

    def delete(self, *keys: str) -> None: ...

    def delete_prefix(self, prefix: str) -> None: ...

    def incr(self, key: str) -> int: ...


class RedisCache:
    name = "redis"

    def __init__(self, client, prefix: str = "hotel:") -> None:
        self.client = client
        self.prefix = prefix

    def get(self, key: str) -> Any | None:
        raw = self.client.get(self.prefix + key)
        return None if raw is None else json.loads(raw)

    def set(self, key: str, value: Any, ttl: int) -> None:
        # SET + EXPIRE одной командой
        self.client.set(self.prefix + key, json.dumps(value, ensure_ascii=False), ex=ttl)

    def delete(self, *keys: str) -> None:
        if keys:
            self.client.delete(*(self.prefix + k for k in keys))

    def delete_prefix(self, prefix: str) -> None:
        keys = list(self.client.scan_iter(match=f"{self.prefix}{prefix}*"))
        if keys:
            self.client.delete(*keys)

    def incr(self, key: str) -> int:
        return self.client.incr(self.prefix + key)


class InMemoryCache:
    name = "memory"

    def __init__(self) -> None:
        self._data: dict[str, tuple[Any, float | None]] = {}

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if item is None:
            return None
        value, expires = item
        if expires is not None and expires < time.monotonic():
            del self._data[key]
            return None
        return json.loads(value)

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._data[key] = (json.dumps(value, ensure_ascii=False), time.monotonic() + ttl)

    def delete(self, *keys: str) -> None:
        for key in keys:
            self._data.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self._data if k.startswith(prefix)]:
            del self._data[key]

    def incr(self, key: str) -> int:
        value = (self.get(key) or 0) + 1
        self._data[key] = (json.dumps(value), None)
        return value


def create_cache(redis_url: str | None) -> Cache:
    if redis_url:
        try:
            import redis
            client = redis.Redis.from_url(redis_url, decode_responses=True,
                                          socket_connect_timeout=1)
            client.ping()
            return RedisCache(client)
        except Exception as error:  # Redis не установлен или не запущен
            print(f"[cache] Redis недоступен ({error}), используется кэш в памяти")
    return InMemoryCache()
