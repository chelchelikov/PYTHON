"""Тест с настоящим Redis; пропускается, если сервер Redis не запущен."""

import pytest

redis = pytest.importorskip("redis")

from cache import RedisCache  # noqa: E402


@pytest.fixture
def redis_cache():
    client = redis.Redis(decode_responses=True, socket_connect_timeout=1)
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Redis не запущен")
    cache = RedisCache(client, prefix="test:hotel:")
    yield cache
    cache.delete_prefix("")


def test_redis_operations(redis_cache):
    redis_cache.set("room:1", {"number": "101"}, ttl=60)
    assert redis_cache.get("room:1") == {"number": "101"}
    assert 0 < redis_cache.client.ttl("test:hotel:room:1") <= 60
    assert redis_cache.incr("views") == 1
    assert redis_cache.incr("views") == 2
    redis_cache.delete("room:1")
    assert redis_cache.get("room:1") is None
