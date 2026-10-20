import os

import redis

from app.mongodb import StorageUnavailable

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def connect_redis(url: str = REDIS_URL) -> redis.Redis:
    client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
    try:
        client.ping()
    except redis.RedisError as error:
        raise StorageUnavailable(f"Redis недоступен ({url}): {error}") from None
    return client
