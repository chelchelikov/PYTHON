from dataclasses import asdict, dataclass
from enum import Enum


class RoomType(Enum):
    STANDARD = "standard"
    DELUXE = "deluxe"
    SUITE = "suite"
    FAMILY = "family"


class RoomStatus(Enum):
    FREE = "free"
    BOOKED = "booked"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"


@dataclass
class Room:
    id: int
    number: str
    room_type: RoomType
    floor: int
    capacity: int
    price: float
    status: RoomStatus

    def to_dict(self) -> dict:
        data = asdict(self)
        data["room_type"] = self.room_type.value
        data["status"] = self.status.value
        return data
