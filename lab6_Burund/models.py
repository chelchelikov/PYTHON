"""Модели предметной области: номера, гости, бронирования."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from exceptions import InvalidStatusError


class RoomStatus(Enum):
    FREE = "свободен"
    OCCUPIED = "занят"
    BOOKED = "забронирован"
    MAINTENANCE = "на обслуживании"


# Разрешённые переходы между состояниями номера
ALLOWED_TRANSITIONS: dict[RoomStatus, set[RoomStatus]] = {
    RoomStatus.FREE: {RoomStatus.BOOKED, RoomStatus.OCCUPIED, RoomStatus.MAINTENANCE},
    RoomStatus.BOOKED: {RoomStatus.OCCUPIED, RoomStatus.FREE},
    RoomStatus.OCCUPIED: {RoomStatus.FREE, RoomStatus.MAINTENANCE},
    RoomStatus.MAINTENANCE: {RoomStatus.FREE},
}


@dataclass
class Entity:
    id: int
    name: str


@dataclass
class Room(Entity):
    floor: int
    price_per_night: float
    capacity: int
    status: RoomStatus = RoomStatus.FREE

    def __post_init__(self) -> None:
        if self.price_per_night <= 0:
            raise ValueError("Цена за ночь должна быть положительной")
        if self.capacity <= 0:
            raise ValueError("Вместимость должна быть положительной")

    @property
    def room_type(self) -> str:
        return "Номер"

    def change_status(self, new_status: RoomStatus) -> None:
        if new_status == self.status:
            return
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStatusError(
                f"Номер {self.name}: нельзя перейти из «{self.status.value}» "
                f"в «{new_status.value}»")
        self.status = new_status

    def night_price(self, guests: int) -> float:
        return self.price_per_night

    def get_report_data(self) -> str:
        return (f"{self.room_type} {self.name} (этаж {self.floor}, мест {self.capacity}): "
                f"{self.price_per_night:.0f} ₽/ночь, {self.status.value}")


@dataclass
class StandardRoom(Room):
    has_window_view: bool = False

    @property
    def room_type(self) -> str:
        return "Стандарт"


@dataclass
class SuiteRoom(Room):
    rooms_count: int = 2
    extra_guest_fee: float = 1500.0

    @property
    def room_type(self) -> str:
        return "Люкс"

    def night_price(self, guests: int) -> float:
        # Первые два гостя включены в цену, остальные оплачиваются отдельно
        extra = max(0, guests - 2)
        return self.price_per_night + extra * self.extra_guest_fee


@dataclass
class Guest(Entity):
    phone: str
    is_vip: bool = False

    def get_report_data(self) -> str:
        vip = " (VIP)" if self.is_vip else ""
        return f"Гость {self.name}{vip}, тел. {self.phone}"


@dataclass
class Booking:
    id: int
    room: Room
    guest: Guest
    check_in: date
    check_out: date
    guests_count: int = 1
    active: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    def get_report_data(self) -> str:
        state = "активно" if self.active else "закрыто"
        return (f"Бронь #{self.id}: {self.guest.name}, номер {self.room.name}, "
                f"{self.check_in:%d.%m.%Y}–{self.check_out:%d.%m.%Y} "
                f"({self.nights} ноч.), {state}")
