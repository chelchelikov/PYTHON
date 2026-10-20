import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fakeredis import aioredis as fake_aioredis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.cache import RedisCache  # noqa: E402
from app.config import Settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import seed  # noqa: E402

TEST_DB = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture
def db():
    database = Database(TEST_DB)
    database.drop_tables()
    seed(database)
    yield database
    database.drop_tables()
    database.engine.dispose()


@pytest.fixture
def cache():
    return RedisCache(fake_aioredis.FakeRedis(decode_responses=True), prefix="test:")


@pytest.fixture
def client(db, cache):
    settings = Settings(database_url=TEST_DB, redis_url=None, log_level="WARNING")
    with TestClient(create_app(settings, db, cache)) as test_client:
        yield test_client
