from datetime import date, timedelta
from unittest.mock import patch

import pytest

from src.exceptions import (BookingConflictError, NotFoundError, OperationNotAllowedError,
                            ValidationError)
from src.models import Booking, BookingStatus, Room
from src.services.booking_service import BookingService
from tests.conftest import TODAY

D = lambda days: TODAY + timedelta(days=days)  # noqa: E731


def existing(start: int, end: int, status=BookingStatus.ACTIVE, booking_id=5) -> Booking:
    return Booking(1, "Петров", D(start), D(end), 2, 7000, status, id=booking_id)


def test_book_free_room_saves_booking(booking_service, booking_repo, room_repo):
    booking = booking_service.book(1, " Иванов ", D(10), D(13), 2)
    assert booking.id == 100
    assert booking.total == 3500 * 3
    room_repo.get.assert_called_once_with(1)
    booking_repo.active_for_room.assert_called_once_with(1)
    saved: Booking = booking_repo.add.call_args.args[0]
    assert saved.guest_name == "Иванов" and saved.status == BookingStatus.ACTIVE


def test_book_overlapping_period_raises_conflict(booking_service, booking_repo):
    booking_repo.active_for_room.return_value = [existing(10, 15)]
    with pytest.raises(BookingConflictError):
        booking_service.book(1, "Иванов", D(12), D(14), 1)
    booking_repo.add.assert_not_called()


def test_book_adjacent_period_is_allowed(booking_service, booking_repo):
    booking_repo.active_for_room.return_value = [existing(10, 15)]
    booking = booking_service.book(1, "Иванов", D(15), D(17), 1)  # заезд в день выезда
    assert booking.check_in == D(15)


def test_book_missing_room(booking_service, room_repo):
    room_repo.get.return_value = None
    with pytest.raises(NotFoundError):
        booking_service.book(99, "Иванов", D(1), D(2), 1)


@pytest.mark.parametrize("guest, check_in, check_out, guests, message", [
    ("", D(1), D(2), 1, "Имя гостя"),
    ("   ", D(1), D(2), 1, "Имя гостя"),
    ("Иванов", D(5), D(5), 1, "позже"),           # 0 ночей
    ("Иванов", D(5), D(3), 1, "позже"),
    ("Иванов", D(1), D(32), 1, "30 ночей"),       # 31 ночь — за пределом
    ("Иванов", D(-1), D(2), 1, "прошедшие"),
    ("Иванов", D(1), D(2), 0, "вмещает"),          # 0 гостей
    ("Иванов", D(1), D(2), 3, "вмещает"),          # больше вместимости (2)
])
def test_book_validation_errors(booking_service, booking_repo, guest, check_in, check_out,
                                guests, message):
    with pytest.raises(ValidationError, match=message):
        booking_service.book(1, guest, check_in, check_out, guests)
    booking_repo.add.assert_not_called()


@pytest.mark.parametrize("nights, expected", [
    (1, 3500.0),
    (6, 21000.0),
    (7, 22050.0),    # с 7 ночей скидка 10 %
    (30, 94500.0),
])
def test_calculate_total_with_long_stay_discount(nights, expected):
    assert BookingService.calculate_total(3500, nights) == expected


def test_cancel_active_booking(booking_service, booking_repo):
    booking_repo.get.return_value = existing(10, 12)
    booking = booking_service.cancel(5)
    assert booking.status == BookingStatus.CANCELLED
    booking_repo.update_status.assert_called_once_with(5, BookingStatus.CANCELLED)


@pytest.mark.parametrize("booking, error", [
    (None, NotFoundError),
    (existing(10, 12, BookingStatus.CANCELLED), OperationNotAllowedError),
    (existing(0, 3), OperationNotAllowedError),     # заезд сегодня — уже началось
    (existing(-2, 1), OperationNotAllowedError),
])
def test_cancel_forbidden_cases(booking_service, booking_repo, booking, error):
    booking_repo.get.return_value = booking
    with pytest.raises(error):
        booking_service.cancel(5)
    booking_repo.update_status.assert_not_called()


def test_find_free_rooms_filters_busy_rooms(booking_service, room_repo, booking_repo):
    rooms = [Room("101", "standard", 2, 3500, 1), Room("102", "standard", 2, 3600, 2),
             Room("201", "suite", 4, 9000, 3)]
    room_repo.list.return_value = rooms
    booking_repo.active_for_room.side_effect = \
        lambda room_id: [existing(10, 15)] if room_id == 2 else []
    free = booking_service.find_free_rooms(D(12), D(14), guests=2)
    assert [r.number for r in free] == ["101", "201"]
    room_repo.list.assert_called_once_with(min_capacity=2)
    assert booking_repo.active_for_room.call_count == 3


def test_find_free_rooms_with_empty_hotel_and_invalid_guests(booking_service, room_repo):
    room_repo.list.return_value = []
    assert booking_service.find_free_rooms(D(1), D(2)) == []
    with pytest.raises(ValidationError):
        booking_service.find_free_rooms(D(1), D(2), guests=0)


def test_default_clock_uses_date_today(room_repo, booking_repo):
    # patch подменяет класс date в модуле сервиса: проверяем работу без внедрённых «часов»
    with patch("src.services.booking_service.date") as fake_date:
        fake_date.today.return_value = date(2030, 1, 1)
        service = BookingService(room_repo, booking_repo, today=fake_date.today)
        with pytest.raises(ValidationError, match="прошедшие"):
            service.book(1, "Иванов", date(2029, 12, 31), date(2030, 1, 2), 1)
        fake_date.today.assert_called()
