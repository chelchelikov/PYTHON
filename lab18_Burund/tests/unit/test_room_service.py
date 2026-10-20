import pytest

from src.exceptions import NotFoundError, OperationNotAllowedError, ValidationError
from src.models import Booking, Room
from src.services.room_service import MAX_CAPACITY, MAX_PRICE, validate_room


def test_create_room_with_valid_data(room_service, room_repo):
    # Arrange — репозиторий-заглушка из conftest
    # Act
    room = room_service.create_room(" 205 ", "deluxe", 3, 5500)
    # Assert
    assert room.id == 10
    room_repo.get_by_number.assert_called_once_with("205")
    saved: Room = room_repo.add.call_args.args[0]
    assert (saved.number, saved.room_type, saved.capacity, saved.price_per_night) == \
        ("205", "deluxe", 3, 5500.0)


def test_create_duplicate_room_is_rejected(room_service, room_repo, room):
    room_repo.get_by_number.return_value = room
    with pytest.raises(ValidationError, match="уже существует"):
        room_service.create_room("101", "standard", 2, 3000)
    room_repo.add.assert_not_called()


@pytest.mark.parametrize("number, room_type, capacity, price", [
    ("", "standard", 2, 3000),                    # пустая строка
    ("12345678901", "standard", 2, 3000),         # длиннее 10 символов
    ("101", "palace", 2, 3000),                   # неизвестный тип
    ("101", "standard", 0, 3000),                 # вместимость 0
    ("101", "standard", MAX_CAPACITY + 1, 3000),  # больше максимума
    ("101", "standard", 2, 0),                    # нулевая цена
    ("101", "standard", 2, MAX_PRICE + 0.01),     # цена за пределом
])
def test_validate_room_rejects_invalid_values(number, room_type, capacity, price):
    with pytest.raises(ValidationError):
        validate_room(number, room_type, capacity, price)


@pytest.mark.parametrize("capacity, price", [(1, 0.01), (MAX_CAPACITY, MAX_PRICE)])
def test_validate_room_accepts_boundary_values(capacity, price):
    validate_room("1", "suite", capacity, price)  # не должно быть исключения


def test_get_room_not_found_and_invalid_id(room_service, room_repo):
    room_repo.get.return_value = None
    with pytest.raises(NotFoundError):
        room_service.get_room(42)
    room_repo.get.assert_called_once_with(42)
    with pytest.raises(ValidationError):
        room_service.get_room(0)


def test_change_price_updates_repository(room_service, room_repo):
    room_service.change_price(1, 4200)
    updated: Room = room_repo.update.call_args.args[0]
    assert updated.price_per_night == 4200.0


def test_delete_room_with_active_bookings_is_forbidden(room_service, booking_repo, room_repo):
    booking_repo.active_for_room.return_value = [Mock_booking()]
    with pytest.raises(OperationNotAllowedError):
        room_service.delete_room(1)
    room_repo.delete.assert_not_called()
    booking_repo.active_for_room.return_value = []
    room_service.delete_room(1)
    room_repo.delete.assert_called_once_with(1)


def Mock_booking() -> Booking:  # noqa: N802 — фабрика тестовых данных
    from datetime import date
    return Booking(1, "Гость", date(2026, 12, 1), date(2026, 12, 3), 1, 7000)
