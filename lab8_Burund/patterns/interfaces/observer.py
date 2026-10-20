from typing import Protocol

from models.entities import Booking
from models.enums import BookingEvent


class BookingObserver(Protocol):
    def update(self, event: BookingEvent, booking: Booking) -> None: ...
