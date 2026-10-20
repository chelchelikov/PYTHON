from datetime import date, timedelta

from interfaces.observer import BookingObserver
from interfaces.repository import Repository
from interfaces.strategies import PricingStrategy
from models.entities import Booking, HotelError, Room
from models.enums import BookingEvent, BookingStatus, RoomStatus


class BookingService:
    def __init__(self, rooms: Repository[Room], bookings: Repository[Booking],
                 strategy: PricingStrategy) -> None:
        self._rooms = rooms
        self._bookings = bookings
        self._strategy = strategy
        self._observers: list[BookingObserver] = []

    # --- Observer ---
    def subscribe(self, observer: BookingObserver) -> None:
        self._observers.append(observer)

    def unsubscribe(self, observer: BookingObserver) -> None:
        self._observers.remove(observer)

    def _notify(self, event: BookingEvent, booking: Booking) -> None:
        for observer in self._observers:
            observer.update(event, booking)

    # --- Strategy ---
    def set_strategy(self, strategy: PricingStrategy) -> None:
        self._strategy = strategy

    @property
    def strategy(self) -> PricingStrategy:
        return self._strategy

    def calculate_cost(self, room: Room, check_in: date, check_out: date) -> float:
        if check_out <= check_in:
            raise HotelError("Дата выезда должна быть позже даты заезда")
        total = 0.0
        night = check_in
        while night < check_out:
            total += self._strategy.night_price(room, night)
            night += timedelta(days=1)
        return round(total, 2)

    # --- бизнес-операции ---
    def add_room(self, room: Room) -> Room:
        self._rooms.add(room)
        return room

    def rooms(self) -> list[Room]:
        return sorted(self._rooms.get_all(), key=lambda r: r.id)

    def free_rooms(self, guests: int = 1) -> list[Room]:
        return [r for r in self.rooms() if r.status == RoomStatus.FREE and r.capacity >= guests]

    def book(self, room_id: int, guest: str, check_in: date, check_out: date,
             guests: int = 1) -> Booking:
        room = self._rooms.get(room_id)
        if room.status != RoomStatus.FREE:
            raise HotelError(f"Номер {room_id} {room.status.value}")
        if guests > room.capacity:
            raise HotelError(f"Номер {room_id} рассчитан на {room.capacity} гостей")
        cost = self.calculate_cost(room, check_in, check_out)
        booking = Booking(self._bookings.next_id(), room_id, guest, check_in, check_out,
                          self._strategy.name, cost)
        room.status = RoomStatus.BOOKED
        self._rooms.update(room)
        self._bookings.add(booking)
        self._notify(BookingEvent.CREATED, booking)
        return booking

    def cancel(self, booking_id: int) -> Booking:
        booking = self._bookings.get(booking_id)
        if booking.status != BookingStatus.ACTIVE:
            raise HotelError(f"Бронь #{booking_id} уже отменена")
        booking.status = BookingStatus.CANCELLED
        room = self._rooms.get(booking.room_id)
        room.status = RoomStatus.FREE
        self._rooms.update(room)
        self._bookings.update(booking)
        self._notify(BookingEvent.CANCELLED, booking)
        return booking

    def bookings(self) -> list[Booking]:
        return self._bookings.get_all()
