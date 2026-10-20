from enum import Enum


class RoomType(Enum):
    STANDARD = "standard"
    SUITE = "suite"
    FAMILY = "family"


class RoomStatus(Enum):
    FREE = "свободен"
    BOOKED = "забронирован"
    OCCUPIED = "занят"


class BookingStatus(Enum):
    ACTIVE = "активно"
    CANCELLED = "отменено"


class BookingEvent(Enum):
    CREATED = "бронирование создано"
    CANCELLED = "бронирование отменено"
