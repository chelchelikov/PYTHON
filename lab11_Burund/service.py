import hashlib
import json
from typing import Any

from cache import Cache
from exceptions import ConflictError
from models import Room
from repository import BookingRepository, RoomRepository
from schemas import validate_booking, validate_room

CACHE_TTL = 60  # секунд


class RoomService:
    """Бизнес-логика номеров. Чтение по схеме cache-aside: Redis → SQL → Redis."""

    def __init__(self, repository: RoomRepository, cache: Cache, ttl: int = CACHE_TTL) -> None:
        self.repository = repository
        self.cache = cache
        self.ttl = ttl
        self.last_source = ""  # "cache" или "db" — для демонстрации и тестов

    @staticmethod
    def _query_key(query: dict[str, Any]) -> str:
        normalized = json.dumps(query, sort_keys=True, default=str)
        return hashlib.md5(normalized.encode()).hexdigest()

    def _invalidate(self, room_id: int | None = None) -> None:
        if room_id is not None:
            self.cache.delete(f"room:{room_id}")
        self.cache.delete_prefix("search:")

    def get_rooms(self, query: dict[str, Any] | None = None) -> list[Room]:
        return self.repository.get_all(query)

    def get_room(self, room_id: int) -> Room:
        key = f"room:{room_id}"
        cached = self.cache.get(key)
        if cached is not None:
            self.last_source = "cache"
            room = Room.from_dict(cached)
        else:
            self.last_source = "db"
            room = self.repository.get_by_id(room_id)
            self.cache.set(key, vars(room), self.ttl)
        self.cache.incr(f"views:room:{room_id}")
        return room

    def views(self, room_id: int) -> int:
        return self.cache.get(f"views:room:{room_id}") or 0

    def available_rooms(self, query: dict[str, Any]) -> list[Room]:
        key = "search:available:" + self._query_key(query)
        cached = self.cache.get(key)
        if cached is not None:
            self.last_source = "cache"
            return [Room.from_dict(item) for item in cached]
        self.last_source = "db"
        rooms = self.repository.find_available(query)
        self.cache.set(key, [vars(room) for room in rooms], self.ttl)
        return rooms

    def create_room(self, data: Any) -> Room:
        room = self.repository.create(validate_room(data))
        self._invalidate()
        return room

    def update_room(self, room_id: int, data: Any) -> Room:
        fields = validate_room(data)
        fields.setdefault("status", "free")
        fields.setdefault("amenities", [])
        room = self.repository.update(room_id, fields)
        self._invalidate(room_id)
        return room

    def patch_room(self, room_id: int, data: Any) -> Room:
        room = self.repository.update(room_id, validate_room(data, partial=True))
        self._invalidate(room_id)
        return room

    def delete_room(self, room_id: int) -> None:
        room = self.repository.get_by_id(room_id)
        if room.status in ("booked", "occupied"):
            raise ConflictError(f"Номер {room.number} занят или забронирован — удалить нельзя")
        self.repository.delete(room_id)
        self._invalidate(room_id)

    def statistics(self) -> dict[str, Any]:
        return self.repository.statistics()


class BookingService:
    def __init__(self, repository: BookingRepository, cache: Cache) -> None:
        self.repository = repository
        self.cache = cache

    def create_booking(self, data: Any):
        fields = validate_booking(data)
        booking_id = self.repository.create(**fields)
        self.cache.delete_prefix("search:")  # результаты поиска свободных номеров устарели
        return self.repository.get(booking_id)

    def get_booking(self, booking_id: int):
        return self.repository.get(booking_id)

    def cancel_booking(self, booking_id: int):
        booking = self.repository.cancel(booking_id)
        self.cache.delete_prefix("search:")
        return booking
