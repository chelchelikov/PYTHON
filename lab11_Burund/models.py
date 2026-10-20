from dataclasses import dataclass, field
from datetime import date


@dataclass
class Room:
    id: int
    number: str
    room_type: str
    floor: int
    capacity: int
    price: float
    status: str
    amenities: list[str] = field(default_factory=list)
    photos: list[str] = field(default_factory=list)

    def to_dict(self, cdn_base_url: str = "") -> dict:
        return {
            "id": self.id,
            "number": self.number,
            "room_type": self.room_type,
            "floor": self.floor,
            "capacity": self.capacity,
            "price": self.price,
            "status": self.status,
            "amenities": self.amenities,
            "photos": [f"{cdn_base_url.rstrip('/')}/{path}" for path in self.photos],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Room":
        return cls(**data)


@dataclass
class BookingItem:
    room_id: int
    room_number: str
    guests: int
    price: float


@dataclass
class Booking:
    id: int
    guest_name: str
    guest_email: str
    check_in: date
    check_out: date
    total_cost: float
    status: str
    rooms: list[BookingItem]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guest": {"name": self.guest_name, "email": self.guest_email},
            "check_in": self.check_in.isoformat(),
            "check_out": self.check_out.isoformat(),
            "nights": (self.check_out - self.check_in).days,
            "total_cost": self.total_cost,
            "status": self.status,
            "rooms": [vars(item) for item in self.rooms],
        }
