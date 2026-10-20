from datetime import date

from models.entities import Booking, Room
from models.enums import BookingStatus, RoomStatus, RoomType


def room_from_dict(data: dict) -> Room:
    return Room(**{**data, "room_type": RoomType[data["room_type"]],
                   "status": RoomStatus[data["status"]]})


def booking_from_dict(data: dict) -> Booking:
    return Booking(**{**data, "check_in": date.fromisoformat(data["check_in"]),
                      "check_out": date.fromisoformat(data["check_out"]),
                      "status": BookingStatus[data["status"]]})
