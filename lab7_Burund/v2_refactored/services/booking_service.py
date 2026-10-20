from datetime import date

from interfaces.notifier import Notifier
from interfaces.repository import Repository
from models.entities import Booking, Room
from models.enums import BookingStatus, RoomStatus
from models.exceptions import BookingError, RoomUnavailableError


class BookingService:
    """Бронирование, заселение и выселение. Зависимости передаются извне (DIP)."""

    def __init__(self, rooms: Repository[Room], bookings: Repository[Booking],
                 notifier: Notifier) -> None:
        self._rooms = rooms
        self._bookings = bookings
        self._notifier = notifier

    @staticmethod
    def calculate_cost(room: Room, check_in: date, check_out: date, guests: int) -> float:
        nights = (check_out - check_in).days
        if nights <= 0:
            raise BookingError("Дата выезда должна быть позже даты заезда")
        if guests <= 0:
            raise BookingError("Количество гостей должно быть положительным")
        return round(room.night_price(guests) * nights, 2)

    def book(self, room_id: int, guest_name: str, contact: str,
             check_in: date, check_out: date, guests: int) -> Booking:
        room = self._rooms.get(room_id)
        if not room.is_available(guests):
            raise RoomUnavailableError(
                f"Номер {room_id} недоступен ({room.status.value}, мест {room.capacity})")
        cost = self.calculate_cost(room, check_in, check_out, guests)
        booking = Booking(self._bookings.next_id(), room_id, guest_name, contact,
                          check_in, check_out, guests, cost)
        room.status = RoomStatus.BOOKED
        self._rooms.update(room)
        self._bookings.add(booking)
        self._notifier.notify(contact, f"Номер {room_id} забронирован на {booking.nights} ноч., "
                                       f"стоимость {cost:.2f} ₽")
        return booking

    def _change(self, booking_id: int, expected: BookingStatus,
                new_status: BookingStatus, room_status: RoomStatus) -> Booking:
        booking = self._bookings.get(booking_id)
        if booking.status != expected:
            raise BookingError(f"Бронь #{booking_id}: операция недоступна "
                               f"в статусе «{booking.status.value}»")
        room = self._rooms.get(booking.room_id)
        booking.status = new_status
        room.status = room_status
        self._bookings.update(booking)
        self._rooms.update(room)
        return booking

    def check_in(self, booking_id: int) -> Booking:
        booking = self._change(booking_id, BookingStatus.ACTIVE,
                               BookingStatus.CHECKED_IN, RoomStatus.OCCUPIED)
        self._notifier.notify(booking.contact, f"Добро пожаловать в номер {booking.room_id}!")
        return booking

    def check_out(self, booking_id: int) -> Booking:
        booking = self._change(booking_id, BookingStatus.CHECKED_IN,
                               BookingStatus.COMPLETED, RoomStatus.FREE)
        self._notifier.notify(booking.contact, f"Спасибо! К оплате {booking.cost:.2f} ₽")
        return booking

    def cancel(self, booking_id: int) -> Booking:
        booking = self._change(booking_id, BookingStatus.ACTIVE,
                               BookingStatus.CANCELLED, RoomStatus.FREE)
        self._notifier.notify(booking.contact, f"Бронь #{booking_id} отменена")
        return booking

    def all_bookings(self) -> list[Booking]:
        return self._bookings.get_all()
