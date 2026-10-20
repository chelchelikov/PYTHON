from datetime import date

import pytest

from exceptions import BookingError, ValidationError
from repository import BookingRepository

BOOKING = {
    "guest": {"name": "Бурунд", "email": "burund@mail.ru"},
    "check_in": "2026-11-02",
    "check_out": "2026-11-04",
    "rooms": [{"room_id": 1, "guests": 2}, {"room_id": 4, "guests": 1}],
}


def test_validation(room_service):
    with pytest.raises(ValidationError):
        room_service.create_room({"number": "", "room_type": "standard", "floor": 1,
                                  "capacity": 2, "price": -100})


def test_cache_aside_room(room_service, cache):
    room_service.get_room(1)
    assert room_service.last_source == "db"
    room_service.get_room(1)
    assert room_service.last_source == "cache"
    assert room_service.views(1) == 2
    room_service.patch_room(1, {"price": 3700})
    assert room_service.get_room(1).price == 3700
    assert room_service.last_source == "db"


def test_search_cache_invalidated_after_booking(room_service, booking_service):
    query = {"check_in": date(2026, 11, 2), "check_out": date(2026, 11, 4)}
    before = room_service.available_rooms(query)
    room_service.available_rooms(query)
    assert room_service.last_source == "cache"
    booking_service.create_booking(BOOKING)
    after = room_service.available_rooms(query)
    assert room_service.last_source == "db"
    assert len(after) == len(before) - 2


def test_booking_transaction_commit(booking_service):
    booking = booking_service.create_booking(BOOKING)
    assert booking.total_cost == (3500 + 5500) * 2
    assert [item.room_number for item in booking.rooms] == ["101", "201"]


def test_booking_transaction_rollback(db, booking_service):
    repo = BookingRepository(db)
    count = repo.count()
    data = dict(BOOKING, rooms=[{"room_id": 1, "guests": 2}, {"room_id": 7, "guests": 2}],
                guest={"name": "Новый", "email": "new@mail.ru"})
    data["check_in"], data["check_out"] = "2026-11-03", "2026-11-06"  # 301 занят
    with pytest.raises(BookingError):
        booking_service.create_booking(data)
    assert repo.count() == count
    with db.connect() as connection:
        guest = connection.execute("SELECT 1 FROM guests WHERE email = ?",
                                   ("new@mail.ru",)).fetchone()
    assert guest is None


def test_capacity_check(booking_service):
    with pytest.raises(BookingError):
        booking_service.create_booking(dict(BOOKING, rooms=[{"room_id": 3, "guests": 2}]))
