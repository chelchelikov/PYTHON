from interfaces.repository import Repository
from models.entities import Room
from models.enums import RoomStatus
from models.exceptions import HotelError


class RoomService:
    """Управление номерным фондом."""

    def __init__(self, rooms: Repository[Room]) -> None:
        self._rooms = rooms

    def add_room(self, room: Room) -> Room:
        self._rooms.add(room)
        return room

    def all_rooms(self) -> list[Room]:
        return sorted(self._rooms.get_all(), key=lambda room: room.id)

    def free_rooms(self, guests: int = 1) -> list[Room]:
        return [room for room in self.all_rooms() if room.is_available(guests)]

    def set_maintenance(self, room_id: int, enabled: bool) -> Room:
        room = self._rooms.get(room_id)
        if enabled and room.status != RoomStatus.FREE:
            raise HotelError(f"Номер {room_id} занят или забронирован")
        if not enabled and room.status != RoomStatus.MAINTENANCE:
            raise HotelError(f"Номер {room_id} не на обслуживании")
        room.status = RoomStatus.MAINTENANCE if enabled else RoomStatus.FREE
        self._rooms.update(room)
        return room
