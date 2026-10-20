from interfaces.repository import ReadableRepository
from models.entities import Booking, Room
from models.enums import BookingStatus, RoomStatus


class ReportService:
    """Формирование отчётов. Зависит только от интерфейса чтения (ISP)."""

    def __init__(self, rooms: ReadableRepository[Room],
                 bookings: ReadableRepository[Booking]) -> None:
        self._rooms = rooms
        self._bookings = bookings

    def occupancy(self) -> float:
        rooms = self._rooms.get_all()
        if not rooms:
            return 0.0
        busy = sum(1 for r in rooms if r.status in (RoomStatus.BOOKED, RoomStatus.OCCUPIED))
        return round(busy / len(rooms) * 100, 1)

    def revenue(self) -> float:
        return sum(b.cost for b in self._bookings.get_all()
                   if b.status != BookingStatus.CANCELLED)

    def summary(self) -> dict[str, object]:
        rooms = self._rooms.get_all()
        bookings = self._bookings.get_all()
        return {
            "Номеров": len(rooms),
            "По статусам": {s.value: sum(1 for r in rooms if r.status == s) for s in RoomStatus},
            "По типам": {kind: sum(1 for r in rooms if r.kind == kind)
                         for kind in sorted({r.kind for r in rooms})},
            "Загрузка, %": self.occupancy(),
            "Бронирований": len(bookings),
            "Выручка, ₽": self.revenue(),
        }
