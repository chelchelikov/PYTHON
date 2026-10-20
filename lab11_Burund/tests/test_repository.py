import pytest

from exceptions import ConflictError, RoomNotFoundError
from repository import RoomRepository


def test_create_and_read(db):
    repo = RoomRepository(db)
    room = repo.create({"number": "501", "room_type": "suite", "floor": 5, "capacity": 4,
                        "price": 15000, "amenities": ["Wi-Fi", "Сауна"]})
    loaded = repo.get_by_id(room.id)
    assert loaded.room_type == "suite"
    assert loaded.amenities == ["Wi-Fi", "Сауна"]


def test_update_and_delete(db):
    repo = RoomRepository(db)
    room = repo.update(3, {"price": 3000, "status": "maintenance"})
    assert (room.price, room.status) == (3000, "maintenance")
    repo.delete(3)
    with pytest.raises(RoomNotFoundError):
        repo.get_by_id(3)


def test_unique_number(db):
    with pytest.raises(ConflictError):
        RoomRepository(db).create({"number": "101", "room_type": "standard", "floor": 1,
                                   "capacity": 2, "price": 1000})


def test_filters_and_sql_injection(db):
    repo = RoomRepository(db)
    rooms = repo.get_all({"room_type": "suite", "sort": "price", "descending": True})
    assert [r.number for r in rooms] == ["401", "301", "302"]
    assert repo.get_all({"amenity": "Вид на море"})[0].number == "401"
    # Значение передаётся параметром и не меняет смысл запроса
    assert repo.get_all({"amenity": "' OR '1'='1"}) == []


def test_available_for_period(db):
    repo = RoomRepository(db)
    # бронь #2: номер 301 занят 2026-11-01 — 2026-11-05
    from datetime import date
    free = repo.find_available({"check_in": date(2026, 11, 2), "check_out": date(2026, 11, 4),
                                "guests": 4})
    numbers = [r.number for r in free]
    assert "301" not in numbers
    assert numbers == ["202", "303", "401"]
