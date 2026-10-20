import time

import pytest

from app.cache import CacheError


def test_write_and_read(cache):
    cache.set_json("room:x", {"number": "101"}, ttl=30)
    assert cache.get_json("room:x") == {"number": "101"}
    assert cache.stats() == {"hits": 1, "misses": 0}


def test_ttl(cache):
    cache.set_json("room:x", {"a": 1}, ttl=30)
    assert 0 < cache.ttl_of("room:x") <= 30
    cache.set_json("room:y", {"a": 1}, ttl=1)
    time.sleep(1.2)
    assert cache.get_json("room:y") is None


def test_structures(cache):
    cache.reset_free(["a", "b"])
    cache.mark_free("b", False)
    assert cache.is_free("a") and not cache.is_free("b")
    for number in ("101", "301", "301"):
        cache.register_view(number)
    assert cache.popular(1) == [("301", 2)]
    for index in range(12):
        cache.remember_search(f"q{index}")
    assert len(cache.recent_searches()) == 10
    assert cache.recent_searches()[0] == "q11"


def test_serialization_errors(cache):
    with pytest.raises(CacheError):
        cache.set_json("bad", {"value": object()})
    cache.client.set(cache._key("broken"), "{not json")
    with pytest.raises(CacheError):
        cache.get_json("broken")
