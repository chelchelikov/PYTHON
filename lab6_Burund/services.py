"""Бизнес-логика гостиницы."""

from datetime import date

from decorators import log_call, require_status, timed
from exceptions import BookingError, EntityNotFoundError
from models import Booking, Guest, Room, RoomStatus, SuiteRoom

VIP_DISCOUNT = 0.10


class HotelService:
    def __init__(self, name: str) -> None:
        self.name = name
        self.rooms: list[Room] = []
        self.guests: list[Guest] = []
        self.bookings: list[Booking] = []

    # --- номера ---
    @log_call
    def add_room(self, room: Room) -> Room:
        if any(r.id == room.id for r in self.rooms):
            raise ValueError(f"Номер с id={room.id} уже существует")
        self.rooms.append(room)
        return room

    def get_room(self, room_id: int) -> Room:
        for room in self.rooms:
            if room.id == room_id:
                return room
        raise EntityNotFoundError(f"Номер с id={room_id} не найден")

    def find_room_by_name(self, name: str) -> Room | None:
        return next((r for r in self.rooms if r.name == name), None)

    @log_call
    def remove_room(self, room_id: int) -> Room:
        room = self.get_room(room_id)
        if any(b.active and b.room is room for b in self.bookings):
            raise BookingError(f"У номера {room.name} есть активные бронирования")
        self.rooms.remove(room)
        return room

    def change_room_status(self, room_id: int, status: RoomStatus) -> Room:
        room = self.get_room(room_id)
        room.change_status(status)
        return room

    def free_rooms(self, guests: int = 1) -> list[Room]:
        return [r for r in self.rooms if r.status == RoomStatus.FREE and r.capacity >= guests]

    # --- гости ---
    def add_guest(self, guest: Guest) -> Guest:
        self.guests.append(guest)
        return guest

    def get_guest(self, guest_id: int) -> Guest:
        for guest in self.guests:
            if guest.id == guest_id:
                return guest
        raise EntityNotFoundError(f"Гость с id={guest_id} не найден")

    # --- операции предметной области ---
    @staticmethod
    def calculate_cost(room: Room, guest: Guest, check_in: date, check_out: date,
                       guests_count: int) -> float:
        nights = (check_out - check_in).days
        if nights <= 0:
            raise BookingError("Дата выезда должна быть позже даты заезда")
        cost = room.night_price(guests_count) * nights
        if guest.is_vip:
            cost *= 1 - VIP_DISCOUNT
        return round(cost, 2)

    @log_call
    @require_status(RoomStatus.FREE)
    def book_room(self, room_id: int, guest_id: int, check_in: date, check_out: date,
                  guests_count: int = 1) -> Booking:
        room = self.get_room(room_id)
        guest = self.get_guest(guest_id)
        if guests_count > room.capacity:
            raise BookingError(f"Номер {room.name} рассчитан на {room.capacity} гостей")
        self.calculate_cost(room, guest, check_in, check_out, guests_count)
        booking = Booking(len(self.bookings) + 1, room, guest, check_in, check_out, guests_count)
        room.change_status(RoomStatus.BOOKED)
        self.bookings.append(booking)
        return booking

    def booking_cost(self, booking: Booking) -> float:
        return self.calculate_cost(booking.room, booking.guest, booking.check_in,
                                   booking.check_out, booking.guests_count)

    @require_status(RoomStatus.BOOKED)
    def check_in(self, room_id: int) -> Room:
        room = self.get_room(room_id)
        room.change_status(RoomStatus.OCCUPIED)
        return room

    @require_status(RoomStatus.OCCUPIED, RoomStatus.BOOKED)
    def check_out(self, room_id: int) -> float:
        room = self.get_room(room_id)
        booking = next((b for b in self.bookings if b.room is room and b.active), None)
        if booking is None:
            raise BookingError(f"Для номера {room.name} нет активного бронирования")
        booking.active = False
        room.change_status(RoomStatus.FREE)
        return self.booking_cost(booking)

    @timed
    def statistics(self) -> dict[str, float | int]:
        if not self.rooms:
            raise ZeroDivisionError("В гостинице нет номеров — статистику посчитать нельзя")
        prices = [r.price_per_night for r in self.rooms]
        busy = len([r for r in self.rooms if r.status in (RoomStatus.OCCUPIED, RoomStatus.BOOKED)])
        by_status = {s.value: sum(1 for r in self.rooms if r.status == s) for s in RoomStatus}
        revenue = sum(map(self.booking_cost, self.bookings))
        return {
            "Всего номеров": len(self.rooms),
            **by_status,
            "Люксов": sum(1 for r in self.rooms if isinstance(r, SuiteRoom)),
            "Загрузка, %": round(busy / len(self.rooms) * 100, 1),
            "Средняя цена за ночь": round(sum(prices) / len(prices), 2),
            "Минимальная цена": min(prices),
            "Максимальная цена": max(prices),
            "Бронирований": len(self.bookings),
            "Сумма по бронированиям": revenue,
        }
