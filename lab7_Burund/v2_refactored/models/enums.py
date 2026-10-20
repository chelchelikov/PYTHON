from enum import Enum


class RoomStatus(Enum):
    FREE = "свободен"
    BOOKED = "забронирован"
    OCCUPIED = "занят"
    MAINTENANCE = "на обслуживании"


class BookingStatus(Enum):
    ACTIVE = "активно"
    CHECKED_IN = "гость заселён"
    COMPLETED = "завершено"
    CANCELLED = "отменено"
