"""Бизнес-логика бота отеля. Не зависит от Telegram."""

from datetime import date

import aiosqlite

from database.repositories import (ActivityRepository, Booking, BookingRepository, Client,
                                   ClientRepository, Room, RoomRepository, RoomType)
from services.validation import MAX_GUESTS, MAX_NIGHTS, InputError


class BookingError(Exception):
    """Нарушение бизнес-правил бронирования."""


class HotelService:
    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.rooms = RoomRepository(connection)
        self.clients = ClientRepository(connection)
        self.bookings = BookingRepository(connection)
        self.activity = ActivityRepository(connection)

    # --- клиенты ---
    async def register(self, telegram_id: int, name: str) -> Client:
        return await self.clients.get_or_create(telegram_id, name or f"Гость {telegram_id}")

    # --- номера ---
    async def room_types(self) -> list[RoomType]:
        return await self.rooms.types()

    async def rooms_of_type(self, type_id: int) -> list[Room]:
        return await self.rooms.all(type_id)

    async def get_room(self, room_id: int) -> Room:
        room = await self.rooms.get(room_id)
        if room is None:
            raise BookingError("Номер не найден")
        return room

    async def search_free(self, check_in: date, check_out: date, guests: int,
                          type_id: int | None = None) -> list[Room]:
        """Поиск свободных номеров по датам, количеству гостей и типу."""
        self._check_period(check_in, check_out)
        return await self.rooms.free(check_in, check_out, guests, type_id)

    @staticmethod
    def _check_period(check_in: date, check_out: date) -> None:
        if check_out <= check_in:
            raise InputError("Дата выезда должна быть позже даты заезда")
        if (check_out - check_in).days > MAX_NIGHTS:
            raise InputError(f"Максимальный срок проживания — {MAX_NIGHTS} ночей")

    # --- бронирования ---
    async def book(self, telegram_id: int, name: str, room_id: int, check_in: date,
                   check_out: date, guests: int) -> Booking:
        self._check_period(check_in, check_out)
        if not 1 <= guests <= MAX_GUESTS:
            raise InputError(f"Количество гостей — от 1 до {MAX_GUESTS}")
        if check_in < date.today():
            raise InputError("Дата заезда уже прошла")
        room = await self.get_room(room_id)
        if not room.is_active:
            raise BookingError(f"Номер {room.number} временно недоступен")
        if guests > room.capacity:
            raise BookingError(f"Номер {room.number} рассчитан на {room.capacity} гостей")
        free_ids = {r.id for r in await self.rooms.free(check_in, check_out, guests)}
        if room.id not in free_ids:
            raise BookingError(f"Номер {room.number} уже занят на эти даты — выберите другой")
        client = await self.register(telegram_id, name)
        total = room.price * (check_out - check_in).days
        return await self.bookings.add(client.id, room.id, check_in, check_out, guests, total)

    async def history(self, telegram_id: int, name: str = "") -> list[Booking]:
        client = await self.register(telegram_id, name)
        return await self.bookings.for_client(client.id)

    async def _own_booking(self, telegram_id: int, booking_id: int) -> Booking:
        booking = await self.bookings.get(booking_id)
        client = await self.register(telegram_id, "")
        if booking is None or booking.client_id != client.id:
            raise BookingError("Бронирование не найдено")
        return booking

    async def get_booking(self, telegram_id: int, booking_id: int) -> Booking:
        return await self._own_booking(telegram_id, booking_id)

    async def cancel(self, telegram_id: int, booking_id: int) -> Booking:
        booking = await self._own_booking(telegram_id, booking_id)
        if booking.status == "cancelled":
            raise BookingError("Бронирование уже отменено")
        if booking.check_in <= date.today():
            raise BookingError("Нельзя отменить бронирование, которое уже началось")
        await self.bookings.set_status(booking_id, "cancelled")
        return await self.bookings.get(booking_id)

    async def change_dates(self, telegram_id: int, booking_id: int, check_in: date,
                           check_out: date) -> Booking:
        booking = await self._own_booking(telegram_id, booking_id)
        if booking.status != "active":
            raise BookingError("Изменить можно только активное бронирование")
        self._check_period(check_in, check_out)
        free = await self.rooms.free(check_in, check_out, booking.guests,
                                     exclude_booking=booking_id)
        if booking.room_id not in {r.id for r in free}:
            raise BookingError("На новые даты номер занят")
        room = await self.get_room(booking.room_id)
        return await self.bookings.update_dates(booking_id, check_in, check_out,
                                                room.price * (check_out - check_in).days)

    async def delete_cancelled(self, telegram_id: int, booking_id: int) -> None:
        booking = await self._own_booking(telegram_id, booking_id)
        if booking.status != "cancelled":
            raise BookingError("Удалить из истории можно только отменённое бронирование")
        await self.bookings.delete(booking_id)

    # --- администрирование ---
    async def add_room(self, number: str, type_name: str, floor: int, capacity: int,
                       price: float) -> Room:
        if await self.rooms.get_by_number(number):
            raise BookingError(f"Номер {number} уже существует")
        room_type = await self.rooms.type_by_name(type_name)
        if room_type is None:
            raise BookingError(f"Неизвестный тип номера: {type_name}")
        if floor < 0 or capacity < 1 or price <= 0:
            raise InputError("Этаж ≥ 0, вместимость ≥ 1, цена > 0")
        return await self.rooms.add(number, room_type.id, floor, capacity, price)

    async def toggle_room(self, number: str) -> Room:
        room = await self.rooms.get_by_number(number)
        if room is None:
            raise BookingError(f"Номер {number} не найден")
        await self.rooms.set_active(room.id, not room.is_active)
        return await self.rooms.get(room.id)

    async def statistics(self) -> dict:
        return {**await self.bookings.statistics(), **await self.activity.statistics(),
                "rooms": await self.rooms.count(),
                "clients": len(await self.clients.all())}

    async def log_action(self, telegram_id: int, action: str) -> None:
        await self.activity.log(telegram_id, action)
