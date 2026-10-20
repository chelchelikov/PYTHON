import pytest

from exceptions import ConflictError, ValidationError
from models import RoomType


def test_filter_and_sort(service):
    rooms = service.get_rooms({"min_price": 4000, "sort": "price", "descending": True})
    assert [r.number for r in rooms] == ["301", "201"]
    assert [r.number for r in service.get_rooms({"room_type": RoomType.FAMILY})] == ["201"]


def test_validation_rejects_bad_data(service):
    with pytest.raises(ValidationError):
        service.create_room({"number": "", "room_type": "standard", "floor": 1,
                             "capacity": 2, "price": -100})
    assert len(service.get_rooms()) == 3


def test_available_rooms(service):
    assert [r.number for r in service.available_rooms()] == ["101", "201"]
    assert [r.number for r in service.available_rooms({"guests": 3})] == ["201"]


def test_duplicate_number_and_delete_booked(service):
    with pytest.raises(ConflictError):
        service.patch_room(1, {"number": "201"})
    with pytest.raises(ConflictError):
        service.delete_room(3)
