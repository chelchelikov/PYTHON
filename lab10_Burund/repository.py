import threading

from exceptions import RoomNotFoundError
from models import Room


class RoomRepository:
    """Хранилище номеров в памяти."""

    def __init__(self) -> None:
        self._rooms: dict[int, Room] = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def get_all(self) -> list[Room]:
        return list(self._rooms.values())

    def get_by_id(self, room_id: int) -> Room:
        room = self._rooms.get(room_id)
        if room is None:
            raise RoomNotFoundError(f"Номер с id={room_id} не найден")
        return room

    def create(self, room: Room) -> Room:
        with self._lock:
            room.id = self._next_id
            self._next_id += 1
            self._rooms[room.id] = room
        return room

    def update(self, room: Room) -> Room:
        self.get_by_id(room.id)
        self._rooms[room.id] = room
        return room

    def delete(self, room_id: int) -> None:
        self.get_by_id(room_id)
        del self._rooms[room_id]
