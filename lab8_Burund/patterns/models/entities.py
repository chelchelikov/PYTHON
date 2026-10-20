from dataclasses import dataclass, field
from datetime import date

from models.enums import BookingStatus, RoomStatus, RoomType


class HotelError(Exception):
    pass


@dataclass
class Room:
    id: int
    room_type: RoomType
    title: str
    base_price: float
    capacity: int
    amenities: list[str] = field(default_factory=list)
    status: RoomStatus = RoomStatus.FREE


@dataclass
class Booking:
    id: int
    room_id: int
    guest: str
    check_in: date
    check_out: date
    tariff: str
    cost: float
    status: BookingStatus = BookingStatus.ACTIVE

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days
