"""Тесты используют настоящие MongoDB и Redis, если они запущены,
иначе — mongomock и fakeredis (тот же API, но в памяти)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.cache import RedisCache  # noqa: E402
from app.mongodb import StorageUnavailable, connect_mongo  # noqa: E402
from app.redis_client import connect_redis  # noqa: E402
from app.repository import MongoRepository  # noqa: E402
from app.service import RoomService, demo_rooms  # noqa: E402


@pytest.fixture
def mongo_db():
    try:
        db = connect_mongo(db_name="hotel_test")
    except StorageUnavailable:
        import mongomock
        db = mongomock.MongoClient()["hotel_test"]
    db["rooms"].drop()
    yield db
    db["rooms"].drop()


@pytest.fixture
def redis_client():
    try:
        client = connect_redis("redis://localhost:6379/15")
    except StorageUnavailable:
        import fakeredis
        client = fakeredis.FakeRedis(decode_responses=True)
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture
def repository(mongo_db):
    repo = MongoRepository(mongo_db)
    repo.create_indexes()
    repo.insert_many(demo_rooms())
    return repo


@pytest.fixture
def cache(redis_client):
    return RedisCache(redis_client, prefix="test:")


@pytest.fixture
def service(repository, cache):
    service = RoomService(repository, cache)
    service.sync_free_set()
    return service
