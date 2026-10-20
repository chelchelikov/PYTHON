"""Observer: независимые подписчики на события бронирования."""

from models.entities import Booking
from models.enums import BookingEvent


class BookingLogger:
    def __init__(self) -> None:
        self.records: list[str] = []

    def update(self, event: BookingEvent, booking: Booking) -> None:
        self.records.append(f"{event.value}: #{booking.id}, номер {booking.room_id}, "
                            f"{booking.guest}")


class GuestNotifier:
    def __init__(self, send=print) -> None:
        self._send = send

    def update(self, event: BookingEvent, booking: Booking) -> None:
        if event == BookingEvent.CREATED:
            text = (f"{booking.guest}, номер {booking.room_id} забронирован на "
                    f"{booking.nights} ноч. Стоимость {booking.cost:.2f} ₽")
        else:
            text = f"{booking.guest}, ваша бронь #{booking.id} отменена"
        self._send(f"[УВЕДОМЛЕНИЕ] {text}")


class BookingStatistics:
    def __init__(self) -> None:
        self.created = 0
        self.cancelled = 0
        self.revenue = 0.0
        self.by_tariff: dict[str, int] = {}

    def update(self, event: BookingEvent, booking: Booking) -> None:
        if event == BookingEvent.CREATED:
            self.created += 1
            self.revenue += booking.cost
            self.by_tariff[booking.tariff] = self.by_tariff.get(booking.tariff, 0) + 1
        elif event == BookingEvent.CANCELLED:
            self.cancelled += 1
            self.revenue -= booking.cost
