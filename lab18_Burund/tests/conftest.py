from datetime import date
from unittest.mock import Mock

import pytest

from src.models import Booking, Room
from src.repositories import BookingRepository, RoomRepository, connect
from src.services import BookingService, RoomService

TODAY = date(2026, 10, 1)  # фиксированная «сегодняшняя» дата для воспроизводимости


@pytest.fixture
def room() -> Room:
    return Room("101", "standard", 2, 3500.0, id=1)


@pytest.fixture
def room_repo(room) -> Mock:
    repo = Mock(spec=RoomRepository)
    repo.get.return_value = room
    repo.get_by_number.return_value = None
    repo.list.return_value = [room]
    repo.add.side_effect = lambda r: Room(r.number, r.room_type, r.capacity,
                                          r.price_per_night, id=10)
    return repo


@pytest.fixture
def booking_repo() -> Mock:
    repo = Mock(spec=BookingRepository)
    repo.active_for_room.return_value = []
    repo.add.side_effect = lambda b: Booking(b.room_id, b.guest_name, b.check_in, b.check_out,
                                             b.guests, b.total, b.status, id=100)
    return repo


@pytest.fixture
def booking_service(room_repo, booking_repo) -> BookingService:
    return BookingService(room_repo, booking_repo, today=lambda: TODAY)


@pytest.fixture
def room_service(room_repo, booking_repo) -> RoomService:
    return RoomService(room_repo, booking_repo)


@pytest.fixture
def db():
    connection = connect(":memory:")
    yield connection
    connection.close()


@pytest.fixture
def real_services(db):
    rooms, bookings = RoomRepository(db), BookingRepository(db)
    return RoomService(rooms, bookings), BookingService(rooms, bookings, today=lambda: TODAY)
