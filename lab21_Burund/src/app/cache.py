"""Кэш меню в Redis. Если Redis недоступен — приложение работает без кэша."""

import json
import logging
from typing import Any

log = logging.getLogger("restaurant.cache")

MENU_PREFIX = "menu:"


class MenuCache:
    def __init__(self, client=None, ttl: int = 60) -> None:
        self.client = client
        self.ttl = ttl

    def get(self, key: str) -> Any | None:
        if self.client is None:
            return None
        try:
            raw = self.client.get(MENU_PREFIX + key)
        except Exception as error:  # Redis упал — работаем дальше без кэша
            log.warning("Redis недоступен (get): %s", error)
            return None
        return None if raw is None else json.loads(raw)

    def set(self, key: str, value: Any) -> None:
        if self.client is None:
            return
        try:
            self.client.set(MENU_PREFIX + key, json.dumps(value, ensure_ascii=False), ex=self.ttl)
        except Exception as error:
            log.warning("Redis недоступен (set): %s", error)

    def invalidate(self) -> None:
        if self.client is None:
            return
        try:
            keys = list(self.client.scan_iter(match=MENU_PREFIX + "*"))
            if keys:
                self.client.delete(*keys)
        except Exception as error:
            log.warning("Redis недоступен (invalidate): %s", error)

    def ping(self) -> str:
        if self.client is None:
            return "disabled"
        try:
            self.client.ping()
            return "healthy"
        except Exception:
            return "unavailable"


def create_cache(redis_url: str | None, ttl: int) -> MenuCache:
    if not redis_url:
        return MenuCache(None, ttl)
    import redis

    client = redis.Redis.from_url(
        redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
    )
    return MenuCache(client, ttl)
