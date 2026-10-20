"""Factory: создание номеров разных типов с типовыми характеристиками."""

from typing import Callable

from models.entities import HotelError, Room
from models.enums import RoomType


def _standard(room_id: int) -> Room:
    return Room(room_id, RoomType.STANDARD, "Стандартный номер", 3500, 2,
                ["Wi-Fi", "душ"])


def _suite(room_id: int) -> Room:
    return Room(room_id, RoomType.SUITE, "Люкс", 9000, 4,
                ["Wi-Fi", "ванна", "мини-бар", "гостиная"])


def _family(room_id: int) -> Room:
    return Room(room_id, RoomType.FAMILY, "Семейный номер", 5500, 5,
                ["Wi-Fi", "детская кровать", "кухня"])


class RoomFactory:
    _creators: dict[RoomType, Callable[[int], Room]] = {
        RoomType.STANDARD: _standard,
        RoomType.SUITE: _suite,
        RoomType.FAMILY: _family,
    }

    @classmethod
    def register(cls, room_type: RoomType, creator: Callable[[int], Room]) -> None:
        cls._creators[room_type] = creator

    @classmethod
    def create(cls, room_type: RoomType | str, room_id: int) -> Room:
        if isinstance(room_type, str):
            try:
                room_type = RoomType(room_type)
            except ValueError:
                raise HotelError(f"Неизвестный тип номера: {room_type}") from None
        return cls._creators[room_type](room_id)
