"""Бизнес-логика: MongoDB — источник истины, Redis — быстрый доступ."""

import json
import time
from typing import Any

from app.cache import RedisCache
from app.models import Features, Room
from app.repository import MongoRepository


class RoomService:
    def __init__(self, repository: MongoRepository, cache: RedisCache) -> None:
        self.repository = repository
        self.cache = cache
        self.last_source = ""

    # --- чтение с кэшированием ---
    def get_room(self, room_id: str) -> Room:
        """Cache-aside: Redis → (промах) MongoDB → Redis."""
        cached = self.cache.get_json(f"room:{room_id}")
        if cached is not None:
            self.last_source = "redis"
            room = Room.from_document(cached)
        else:
            self.last_source = "mongodb"
            room = self.repository.get(room_id)
            self.cache.set_json(f"room:{room_id}", room.to_dict())
        self.cache.register_view(room.number)
        return room

    def free_rooms(self, room_type: str | None = None, min_beds: int = 1,
                   max_price: float | None = None) -> list[Room]:
        key = f"search:free:{room_type or 'any'}:{min_beds}:{max_price or 'any'}"
        self.cache.remember_search(f"тип={room_type or 'любой'}, мест>={min_beds}, "
                                   f"цена<={max_price or 'любая'}")
        cached = self.cache.get_json(key)
        if cached is not None:
            self.last_source = "redis"
            return [Room.from_document(d) for d in cached]
        self.last_source = "mongodb"
        rooms = self.repository.free_rooms(room_type, min_beds, max_price)
        self.cache.set_json(key, [r.to_dict() for r in rooms], ttl=60)
        return rooms

    # --- изменение с инвалидацией ---
    def _invalidate(self, room: Room | None = None, room_id: str | None = None) -> None:
        if room_id:
            self.cache.delete(f"room:{room_id}")
        self.cache.delete_pattern("search:*")
        if room is not None and room.id:
            self.cache.mark_free(room.id, room.state == "free")

    def add_room(self, room: Room) -> Room:
        room = self.repository.add(room)
        self._invalidate(room)
        return room

    def update_room(self, room_id: str, changes: dict[str, Any]) -> Room:
        room = self.repository.update(room_id, changes)
        self._invalidate(room, room_id)
        return room

    def delete_room(self, room_id: str) -> None:
        self.repository.delete(room_id)
        self._invalidate(room_id=room_id)
        self.cache.mark_free(room_id, False)

    # --- прочее ---
    def list_rooms(self) -> list[Room]:
        return self.repository.list_all()

    def search(self, kind: str, value: str) -> list[Room]:
        queries = {
            "type": lambda: self.repository.by_type(value),
            "view": lambda: self.repository.with_view(value),
            "amenity": lambda: self.repository.with_amenity(value),
            "price": lambda: self.repository.by_price_range(*map(float, value.split("-"))),
        }
        if kind not in queries:
            raise ValueError(f"Неизвестный вид поиска: {kind}")
        return queries[kind]()

    def statistics(self) -> dict[str, Any]:
        return {
            "total": self.repository.count(),
            "by_type": self.repository.stats_by_type(),
            "by_state": self.repository.stats_by_state(),
            "amenities": self.repository.amenity_popularity(),
            "most_expensive": [(r.number, r.price) for r in self.repository.most_expensive()],
            "popular_in_redis": self.cache.popular(),
        }

    def sync_free_set(self) -> int:
        free = self.repository.find({"state": "free"})
        self.cache.reset_free([r.id for r in free])
        return len(free)

    def benchmark(self, room_id: str, counts: tuple[int, ...] = (100, 1000, 10000)
                  ) -> list[dict[str, float]]:
        """Сравнение чтения одного документа из MongoDB и из Redis."""
        self.cache.set_json(f"bench:{room_id}", self.repository.get(room_id).to_dict())
        key = self.cache._key(f"bench:{room_id}")
        results = []
        for count in counts:
            start = time.perf_counter()
            for _ in range(count):
                self.repository.get(room_id)
            mongo = time.perf_counter() - start
            start = time.perf_counter()
            for _ in range(count):
                Room.from_document(json.loads(self.cache.client.get(key)))
            redis_time = time.perf_counter() - start
            results.append({"count": count, "mongo_total": mongo, "redis_total": redis_time,
                            "mongo_avg_ms": mongo / count * 1000,
                            "redis_avg_ms": redis_time / count * 1000})
        self.cache.delete(f"bench:{room_id}")
        return results


def demo_rooms() -> list[Room]:
    """20+ номеров для заполнения коллекции."""
    data = [
        ("101", "standard", 1, 3500, "free", 18, 1, "courtyard", [], ["wifi", "tv"]),
        ("102", "standard", 1, 3200, "occupied", 18, 1, "courtyard", [], ["wifi", "tv"]),
        ("103", "standard", 1, 3400, "free", 20, 2, "park", [], ["wifi", "tv", "fridge"]),
        ("104", "standard", 1, 2900, "maintenance", 16, 1, "courtyard", [], ["wifi"]),
        ("105", "family", 1, 5800, "free", 32, 3, "park", ["balcony"], ["wifi", "tv", "kitchen", "crib"]),
        ("201", "deluxe", 2, 5500, "free", 26, 2, "city", ["balcony"], ["wifi", "tv", "minibar", "air_conditioning"]),
        ("202", "deluxe", 2, 5700, "booked", 26, 2, "city", [], ["wifi", "tv", "minibar"]),
        ("203", "deluxe", 2, 6200, "free", 28, 2, "sea", ["balcony"], ["wifi", "tv", "minibar", "air_conditioning"]),
        ("204", "family", 2, 6000, "free", 34, 4, "park", [], ["wifi", "tv", "kitchen", "crib"]),
        ("205", "standard", 2, 3600, "free", 18, 2, "city", [], ["wifi", "tv"]),
        ("206", "standard", 2, 3700, "occupied", 19, 2, "city", ["smoking"], ["wifi", "tv"]),
        ("301", "suite", 3, 9000, "booked", 45, 2, "sea", ["balcony"], ["wifi", "tv", "minibar", "bathtub", "air_conditioning"]),
        ("302", "suite", 3, 8500, "free", 42, 2, "sea", ["balcony"], ["wifi", "tv", "minibar", "bathtub"]),
        ("303", "family", 3, 7000, "free", 38, 4, "sea", ["balcony"], ["wifi", "tv", "kitchen", "crib", "air_conditioning"]),
        ("304", "deluxe", 3, 6400, "occupied", 27, 2, "sea", [], ["wifi", "tv", "minibar"]),
        ("305", "deluxe", 3, 6100, "free", 26, 3, "park", [], ["wifi", "tv", "minibar", "air_conditioning"]),
        ("401", "suite", 4, 12000, "free", 60, 3, "sea", ["balcony"], ["wifi", "tv", "minibar", "bathtub", "air_conditioning", "jacuzzi"]),
        ("402", "suite", 4, 11000, "maintenance", 55, 2, "city", ["balcony"], ["wifi", "tv", "minibar", "bathtub"]),
        ("403", "standard", 4, 3900, "free", 20, 2, "city", [], ["wifi", "tv", "air_conditioning"]),
        ("404", "family", 4, 7500, "booked", 40, 5, "park", ["balcony"], ["wifi", "tv", "kitchen", "crib"]),
        ("405", "deluxe", 4, 6800, "free", 30, 2, "sea", ["balcony"], ["wifi", "tv", "minibar", "bathtub"]),
        ("501", "suite", 5, 15000, "free", 75, 4, "sea", ["balcony"], ["wifi", "tv", "minibar", "bathtub", "air_conditioning", "jacuzzi", "kitchen"]),
    ]
    rooms = []
    for number, room_type, floor, price, state, area, beds, view, flags, amenities in data:
        features = Features(area, beds, view, smoking="smoking" in flags, balcony="balcony" in flags)
        rooms.append(Room(number, room_type, floor, price, state, features, amenities))
    return rooms
