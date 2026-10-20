import pytest

from exceptions import RoomNotFoundError
from models import Room, RoomStatus, RoomType
from repository import RoomRepository


def make_room(number: str = "101") -> Room:
    return Room(0, number, RoomType.STANDARD, 1, 2, 3000, RoomStatus.FREE)


def test_create_assigns_ids():
    repo = RoomRepository()
    first, second = repo.create(make_room("1")), repo.create(make_room("2"))
    assert (first.id, second.id) == (1, 2)
    assert repo.get_by_id(2) is second


def test_delete_and_not_found():
    repo = RoomRepository()
    room = repo.create(make_room())
    repo.delete(room.id)
    with pytest.raises(RoomNotFoundError):
        repo.get_by_id(room.id)
