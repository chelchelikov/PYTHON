from collections.abc import Callable
from datetime import date

from src.exceptions import (BookingConflictError, NotFoundError, OperationNotAllowedError,
                            ValidationError)
from src.models import Booking, BookingStatus, DateRange, Room

MAX_NIGHTS = 30
LONG_STAY_NIGHTS = 7
LONG_STAY_DISCOUNT = 0.10


class BookingService:
    def __init__(self, rooms, bookings, today: Callable[[], date] = date.today) -> None:
        self.rooms = rooms
        self.bookings = bookings
        self.today = today  # подменяется в тестах, чтобы результат не зависел от даты запуска

    def _period(self, check_in: date, check_out: date) -> DateRange:
        period = DateRange(check_in, check_out)
        if period.nights < 1:
            raise ValidationError("Дата выезда должна быть позже даты заезда")
        if period.nights > MAX_NIGHTS:
            raise ValidationError(f"Максимальный срок проживания — {MAX_NIGHTS} ночей")
        if check_in < self.today():
            raise ValidationError("Нельзя бронировать на прошедшие даты")
        return period

    @staticmethod
    def calculate_total(price_per_night: float, nights: int) -> float:
        total = price_per_night * nights
        if nights >= LONG_STAY_NIGHTS:
            total *= 1 - LONG_STAY_DISCOUNT
        return round(total, 2)

    def is_free(self, room_id: int, period: DateRange) -> bool:
        return not any(b.period.overlaps(period) for b in self.bookings.active_for_room(room_id))

    def book(self, room_id: int, guest_name: str, check_in: date, check_out: date,
             guests: int) -> Booking:
        if not guest_name or not guest_name.strip():
            raise ValidationError("Имя гостя обязательно")
        period = self._period(check_in, check_out)
        room = self.rooms.get(room_id)
        if room is None:
            raise NotFoundError(f"Номер с id={room_id} не найден")
        if not 1 <= guests <= room.capacity:
            raise ValidationError(f"Номер {room.number} вмещает от 1 до {room.capacity} гостей")
        if not self.is_free(room_id, period):
            raise BookingConflictError(f"Номер {room.number} занят в выбранный период")
        booking = Booking(room_id, guest_name.strip(), check_in, check_out, guests,
                          self.calculate_total(room.price_per_night, period.nights))
        return self.bookings.add(booking)

    def cancel(self, booking_id: int) -> Booking:
        booking = self.bookings.get(booking_id)
        if booking is None:
            raise NotFoundError(f"Бронирование #{booking_id} не найдено")
        if not booking.is_active:
            raise OperationNotAllowedError("Бронирование уже отменено")
        if booking.check_in <= self.today():
            raise OperationNotAllowedError("Нельзя отменить начавшееся бронирование")
        self.bookings.update_status(booking_id, BookingStatus.CANCELLED)
        booking.status = BookingStatus.CANCELLED
        return booking

    def find_free_rooms(self, check_in: date, check_out: date, guests: int = 1) -> list[Room]:
        if guests < 1:
            raise ValidationError("Количество гостей должно быть не меньше 1")
        period = self._period(check_in, check_out)
        return [room for room in self.rooms.list(min_capacity=guests)
                if self.is_free(room.id, period)]

    def guest_history(self, guest_name: str) -> list[Booking]:
        return self.bookings.for_guest(guest_name)
