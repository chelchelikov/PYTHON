"""RedisCache: кэш и быстрые структуры данных для отеля.

Используемые типы Redis:
  String      room:{id}, search:free:{параметры} — кэш JSON с TTL (cache-aside)
  Set         rooms:free — id свободных номеров (быстрая проверка доступности)
  Sorted Set  rooms:popular — рейтинг просмотров номеров
  List        searches:recent — последние поисковые запросы
  Hash        cache:stats — счётчики попаданий и промахов кэша
"""

import json
from typing import Any

import redis

DEFAULT_TTL = 120  # секунд
RECENT_SEARCHES = 10


class CacheError(Exception):
    pass


class RedisCache:
    def __init__(self, client: redis.Redis, prefix: str = "lab13:", ttl: int = DEFAULT_TTL) -> None:
        self.client = client
        self.prefix = prefix
        self.ttl = ttl

    def _key(self, key: str) -> str:
        return self.prefix + key

    # --- String + TTL ---
    def get_json(self, key: str) -> Any | None:
        raw = self.client.get(self._key(key))
        if raw is None:
            self.client.hincrby(self._key("cache:stats"), "misses", 1)
            return None
        self.client.hincrby(self._key("cache:stats"), "hits", 1)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self.client.delete(self._key(key))
            raise CacheError(f"Повреждённое значение в кэше: {key}") from None

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        try:
            payload = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as error:
            raise CacheError(f"Не удалось сериализовать {key}: {error}") from None
        self.client.set(self._key(key), payload, ex=ttl or self.ttl)

    def delete(self, *keys: str) -> int:
        return self.client.delete(*(self._key(k) for k in keys)) if keys else 0

    def ttl_of(self, key: str) -> int:
        return self.client.ttl(self._key(key))

    def exists(self, key: str) -> bool:
        return bool(self.client.exists(self._key(key)))

    def delete_pattern(self, pattern: str) -> int:
        keys = list(self.client.scan_iter(match=self._key(pattern)))
        return self.client.delete(*keys) if keys else 0

    # --- Set: свободные номера ---
    def mark_free(self, room_id: str, is_free: bool) -> None:
        if is_free:
            self.client.sadd(self._key("rooms:free"), room_id)
        else:
            self.client.srem(self._key("rooms:free"), room_id)

    def is_free(self, room_id: str) -> bool:
        return bool(self.client.sismember(self._key("rooms:free"), room_id))

    def free_count(self) -> int:
        return self.client.scard(self._key("rooms:free"))

    def reset_free(self, room_ids: list[str]) -> None:
        pipe = self.client.pipeline()
        pipe.delete(self._key("rooms:free"))
        if room_ids:
            pipe.sadd(self._key("rooms:free"), *room_ids)
        pipe.execute()

    # --- Sorted Set: популярность ---
    def register_view(self, room_number: str) -> float:
        return self.client.zincrby(self._key("rooms:popular"), 1, room_number)

    def popular(self, limit: int = 5) -> list[tuple[str, int]]:
        items = self.client.zrevrange(self._key("rooms:popular"), 0, limit - 1, withscores=True)
        return [(number, int(score)) for number, score in items]

    # --- List: последние запросы ---
    def remember_search(self, description: str) -> None:
        pipe = self.client.pipeline()
        pipe.lpush(self._key("searches:recent"), description)
        pipe.ltrim(self._key("searches:recent"), 0, RECENT_SEARCHES - 1)
        pipe.execute()

    def recent_searches(self) -> list[str]:
        return self.client.lrange(self._key("searches:recent"), 0, -1)

    # --- Hash: статистика ---
    def stats(self) -> dict[str, int]:
        raw = self.client.hgetall(self._key("cache:stats"))
        return {"hits": int(raw.get("hits", 0)), "misses": int(raw.get("misses", 0))}

    def status(self) -> dict[str, Any]:
        keys = sorted(k[len(self.prefix):] for k in self.client.scan_iter(match=self._key("*")))
        return {
            "keys": keys,
            "ttl": {k: self.ttl_of(k) for k in keys if k.startswith(("room:", "search:"))},
            "free_rooms": self.free_count(),
            **self.stats(),
        }

    def clear(self) -> int:
        return self.delete_pattern("*")
