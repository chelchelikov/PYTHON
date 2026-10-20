from dataclasses import replace
from typing import Any

from exceptions import ConflictError
from models import Room, RoomStatus
from repository import RoomRepository
from schemas import validate_room


class RoomService:
    def __init__(self, repository: RoomRepository) -> None:
        self.repository = repository

    def _check_unique_number(self, number: str, room_id: int | None = None) -> None:
        for room in self.repository.get_all():
            if room.number == number and room.id != room_id:
                raise ConflictError(f"Номер {number} уже существует")

    def get_rooms(self, query: dict[str, Any] | None = None) -> list[Room]:
        query = query or {}
        rooms = self.repository.get_all()
        if "room_type" in query:
            rooms = [r for r in rooms if r.room_type == query["room_type"]]
        if "status" in query:
            rooms = [r for r in rooms if r.status == query["status"]]
        if "floor" in query:
            rooms = [r for r in rooms if r.floor == query["floor"]]
        if "min_capacity" in query:
            rooms = [r for r in rooms if r.capacity >= query["min_capacity"]]
        if "min_price" in query:
            rooms = [r for r in rooms if r.price >= query["min_price"]]
        if "max_price" in query:
            rooms = [r for r in rooms if r.price <= query["max_price"]]
        sort = query.get("sort") or "id"
        return sorted(rooms, key=lambda r: getattr(r, sort), reverse=query.get("descending", False))

    def get_room(self, room_id: int) -> Room:
        return self.repository.get_by_id(room_id)

    def create_room(self, data: Any) -> Room:
        fields = validate_room(data)
        self._check_unique_number(fields["number"])
        fields.setdefault("status", RoomStatus.FREE)
        return self.repository.create(Room(id=0, **fields))

    def update_room(self, room_id: int, data: Any) -> Room:
        fields = validate_room(data)
        self.repository.get_by_id(room_id)
        self._check_unique_number(fields["number"], room_id)
        fields.setdefault("status", RoomStatus.FREE)
        return self.repository.update(Room(id=room_id, **fields))

    def patch_room(self, room_id: int, data: Any) -> Room:
        fields = validate_room(data, partial=True)
        room = self.repository.get_by_id(room_id)
        if "number" in fields:
            self._check_unique_number(fields["number"], room_id)
        return self.repository.update(replace(room, **fields))

    def delete_room(self, room_id: int) -> None:
        room = self.repository.get_by_id(room_id)
        if room.status in (RoomStatus.BOOKED, RoomStatus.OCCUPIED):
            raise ConflictError(f"Номер {room.number} занят или забронирован — удалить нельзя")
        self.repository.delete(room_id)

    def available_rooms(self, query: dict[str, Any] | None = None) -> list[Room]:
        """Свободные номера; guests — минимальная вместимость. Самые дешёвые — первыми."""
        query = dict(query or {})
        query["status"] = RoomStatus.FREE
        if "guests" in query:
            query["min_capacity"] = query.pop("guests")
        if not query.get("sort"):
            query["sort"] = "price"
        return self.get_rooms(query)

    def statistics(self) -> dict[str, Any]:
        rooms = self.repository.get_all()
        free = [r for r in rooms if r.status == RoomStatus.FREE]
        return {
            "rooms_count": len(rooms),
            "available_count": len(free),
            "occupancy_percent": round((1 - len(free) / len(rooms)) * 100, 1) if rooms else 0.0,
            "average_price": round(sum(r.price for r in rooms) / len(rooms), 2) if rooms else 0.0,
        }
