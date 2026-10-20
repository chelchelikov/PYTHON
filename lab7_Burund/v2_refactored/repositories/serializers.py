"""Преобразование сущностей в словари и обратно для файлового хранилища."""

from dataclasses import asdict
from datetime import date
from typing import Any

from models.entities import Booking, Room
from models.enums import BookingStatus, RoomStatus


def _room_classes(base: type = Room) -> dict[str, type]:
    # Подклассы находятся автоматически: новый тип номера не требует правок здесь
    classes = {}
    for cls in base.__subclasses__():
        classes[cls.__name__] = cls
        classes.update(_room_classes(cls))
    return classes


def room_to_dict(room: Room) -> dict[str, Any]:
    data = asdict(room)
    data["status"] = room.status.name
    data["type"] = type(room).__name__
    return data


def room_from_dict(data: dict[str, Any]) -> Room:
    data = dict(data)
    cls = _room_classes()[data.pop("type")]
    data["status"] = RoomStatus[data["status"]]
    return cls(**data)


def booking_to_dict(booking: Booking) -> dict[str, Any]:
    data = asdict(booking)
    data["status"] = booking.status.name
    data["check_in"] = booking.check_in.isoformat()
    data["check_out"] = booking.check_out.isoformat()
    return data


def booking_from_dict(data: dict[str, Any]) -> Booking:
    data = dict(data)
    data["status"] = BookingStatus[data["status"]]
    data["check_in"] = date.fromisoformat(data["check_in"])
    data["check_out"] = date.fromisoformat(data["check_out"])
    return Booking(**data)
