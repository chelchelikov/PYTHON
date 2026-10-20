import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from cache import InMemoryCache  # noqa: E402
from database import Database  # noqa: E402
from repository import BookingRepository, RoomRepository  # noqa: E402
from service import BookingService, RoomService  # noqa: E402


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    database.init(seed=True)
    return database


@pytest.fixture
def cache():
    return InMemoryCache()


@pytest.fixture
def room_service(db, cache):
    return RoomService(RoomRepository(db), cache)


@pytest.fixture
def booking_service(db, cache):
    return BookingService(BookingRepository(db), cache)


@pytest.fixture
def client(db, cache):
    app = create_app(db, cache, cdn_base_url="http://cdn.test/static")
    app.testing = True
    return app.test_client()
