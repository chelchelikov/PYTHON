"""Интеграционные тесты: Service + Repository + SQLite без заглушек."""

from datetime import timedelta

import pytest

from src.exceptions import BookingConflictError, OperationNotAllowedError
from src.main import main
from tests.conftest import TODAY

pytestmark = pytest.mark.integration
D = lambda days: TODAY + timedelta(days=days)  # noqa: E731


def test_full_booking_cycle(real_services):
    rooms, bookings = real_services
    standard = rooms.create_room("101", "standard", 2, 3500)
    suite = rooms.create_room("301", "suite", 4, 9000)

    first = bookings.book(standard.id, "Иванов", D(5), D(8), 2)
    assert first.id is not None and first.total == 10500

    with pytest.raises(BookingConflictError):
        bookings.book(standard.id, "Петров", D(7), D(9), 1)

    free = bookings.find_free_rooms(D(6), D(7), guests=2)
    assert [r.number for r in free] == ["301"]

    bookings.cancel(first.id)
    free = bookings.find_free_rooms(D(6), D(7), guests=2)
    assert [r.number for r in free] == ["101", "301"]
    assert [b.status.value for b in bookings.guest_history("Иванов")] == ["cancelled"]
    assert suite.id != standard.id


def test_room_with_bookings_cannot_be_deleted(real_services, db):
    rooms, bookings = real_services
    room = rooms.create_room("102", "deluxe", 2, 5000)
    booking = bookings.book(room.id, "Сидоров", D(3), D(4), 1)
    with pytest.raises(OperationNotAllowedError):
        rooms.delete_room(room.id)
    bookings.cancel(booking.id)
    rooms.delete_room(room.id)
    assert db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0


def test_cli_end_to_end(tmp_path, capsys):
    db_file = str(tmp_path / "hotel.db")
    future = TODAY.replace(year=TODAY.year + 1)
    assert main(["--db", db_file, "add-room", "101", "standard", "2", "3500"]) == 0
    assert main(["--db", db_file, "book", "1", "Бурунд", future.isoformat(),
                 (future + timedelta(days=2)).isoformat(), "--guests", "2"]) == 0
    assert main(["--db", db_file, "book", "1", "Другой", future.isoformat(),
                 (future + timedelta(days=1)).isoformat()]) == 1
    output = capsys.readouterr().out
    assert "Создан номер 101" in output
    assert "7000.00 ₽" in output
    assert "занят" in output
