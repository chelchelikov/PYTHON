"""Сущности предметной области.

Ремонт номера — это состояние (RoomStatus.MAINTENANCE), а не отдельный подкласс,
поэтому любой наследник Room соблюдает контракт базового класса (LSP).
Стоимость ночи вычисляет сам номер — новый тип номера добавляется
новым классом без изменения сервисов (OCP).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

from models.enums import BookingStatus, RoomStatus


@dataclass
class Room(ABC):
    id: int
    floor: int
    base_price: float
    capacity: int
    status: RoomStatus = RoomStatus.FREE

    def __post_init__(self) -> None:
        if self.base_price <= 0:
            raise ValueError("Цена должна быть положительной")
        if self.capacity <= 0:
            raise ValueError("Вместимость должна быть положительной")

    @property
    @abstractmethod
    def kind(self) -> str:
        ...

    @abstractmethod
    def night_price(self, guests: int) -> float:
        ...

    def is_available(self, guests: int = 1) -> bool:
        return self.status == RoomStatus.FREE and guests <= self.capacity


@dataclass
class StandardRoom(Room):
    @property
    def kind(self) -> str:
        return "Стандарт"

    def night_price(self, guests: int) -> float:
        return self.base_price


@dataclass
class SuiteRoom(Room):
    extra_guest_fee: float = 1500.0

    @property
    def kind(self) -> str:
        return "Люкс"

    def night_price(self, guests: int) -> float:
        return self.base_price + max(0, guests - 2) * self.extra_guest_fee


@dataclass
class FamilyRoom(Room):
    family_discount: float = 0.1

    @property
    def kind(self) -> str:
        return "Семейный"

    def night_price(self, guests: int) -> float:
        if guests >= 3:
            return self.base_price * (1 - self.family_discount)
        return self.base_price


@dataclass
class Booking:
    id: int
    room_id: int
    guest_name: str
    contact: str
    check_in: date
    check_out: date
    guests: int
    cost: float
    status: BookingStatus = BookingStatus.ACTIVE
    history: list[str] = field(default_factory=list)

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days
