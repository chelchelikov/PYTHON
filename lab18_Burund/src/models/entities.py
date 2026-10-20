from dataclasses import dataclass
from datetime import date
from enum import Enum


class BookingStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class DateRange:
    """Период проживания [check_in, check_out): день выезда не занят."""

    check_in: date
    check_out: date

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    def overlaps(self, other: "DateRange") -> bool:
        return self.check_in < other.check_out and other.check_in < self.check_out


@dataclass
class Room:
    number: str
    room_type: str
    capacity: int
    price_per_night: float
    id: int | None = None


@dataclass
class Booking:
    room_id: int
    guest_name: str
    check_in: date
    check_out: date
    guests: int
    total: float
    status: BookingStatus = BookingStatus.ACTIVE
    id: int | None = None

    @property
    def period(self) -> DateRange:
        return DateRange(self.check_in, self.check_out)

    @property
    def is_active(self) -> bool:
        return self.status == BookingStatus.ACTIVE
