import asyncio

import pytest

from app.repositories.room import RoomRepository
from app.schemas.room import RoomCreate, RoomPatch
from app.services.room import RoomConflict, RoomNotFound, RoomService


@pytest.fixture
def service(db, cache):
    session = db.session_factory()
    yield RoomService(RoomRepository(session), cache, ttl=60)
    session.close()


def test_create_and_conflict(service):
    room = service.create(RoomCreate(number="601", room_type="deluxe", floor=6, capacity=2,
                                     price=7000))
    assert room.id is not None
    with pytest.raises(RoomConflict):
        service.create(RoomCreate(number="601", room_type="deluxe", floor=6, capacity=2,
                                  price=7000))


def test_async_get_uses_cache(service, cache):
    room = asyncio.run(service.get_room(1))
    assert service.last_source == "db"
    assert asyncio.run(cache.get("room:1"))["number"] == room.number
    asyncio.run(service.get_room(1))
    assert service.last_source == "cache"


def test_patch_invalidates_and_missing(service, cache):
    asyncio.run(service.get_room(4))
    asyncio.run(service.patch(4, RoomPatch(price=100)))
    assert asyncio.run(cache.get("room:4")) is None
    with pytest.raises(RoomNotFound):
        asyncio.run(service.patch(999, RoomPatch(price=100)))
