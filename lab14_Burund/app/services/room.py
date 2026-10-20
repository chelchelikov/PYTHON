from typing import Any

from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.cache import Cache
from app.models.room import Room
from app.repositories.room import RoomRepository
from app.schemas.room import RoomCreate, RoomPatch, RoomResponse


class RoomNotFound(Exception):
    def __init__(self, room_id: int) -> None:
        super().__init__(f"Номер с id={room_id} не найден")


class RoomConflict(Exception):
    pass


class RoomService:
    def __init__(self, repository: RoomRepository, cache: Cache, ttl: int) -> None:
        self.repository = repository
        self.cache = cache
        self.ttl = ttl
        self.last_source = ""

    @staticmethod
    def _key(room_id: int) -> str:
        return f"room:{room_id}"

    def _get_or_404(self, room_id: int) -> Room:
        room = self.repository.get(room_id)
        if room is None:
            raise RoomNotFound(room_id)
        return room

    def _ensure_unique(self, number: str, room_id: int | None = None) -> None:
        existing = self.repository.get_by_number(number)
        if existing is not None and existing.id != room_id:
            raise RoomConflict(f"Номер {number} уже существует")

    def _commit(self, action) -> Room:
        try:
            return action()
        except IntegrityError:
            self.repository.rollback()
            raise RoomConflict("Нарушено ограничение уникальности или целостности") from None

    async def get_room(self, room_id: int) -> RoomResponse:
        """Асинхронное чтение с кэшем: await Redis, БД — в пуле потоков."""
        cached = await self.cache.get(self._key(room_id))
        if cached is not None:
            self.last_source = "cache"
            return RoomResponse.model_validate(cached)
        self.last_source = "db"
        room = await run_in_threadpool(self._get_or_404, room_id)
        response = RoomResponse.model_validate(room)
        await self.cache.set(self._key(room_id), response.model_dump(mode="json"), self.ttl)
        return response

    def list_rooms(self, filters: dict[str, Any], sort: str, descending: bool, limit: int,
                   offset: int) -> tuple[int, list[Room]]:
        return self.repository.list_rooms(filters, sort, descending, limit, offset)

    def search(self, text: str, limit: int) -> list[Room]:
        return self.repository.search(text, limit)

    def create(self, data: RoomCreate) -> Room:
        self._ensure_unique(data.number)
        room = Room(**data.model_dump(mode="json"))
        return self._commit(lambda: self.repository.add(room))

    def _replace_sync(self, room_id: int, data: RoomCreate) -> Room:
        room = self._get_or_404(room_id)
        self._ensure_unique(data.number, room_id)
        for key, value in data.model_dump(mode="json").items():
            setattr(room, key, value)
        return self._commit(lambda: self.repository.save(room))

    def _patch_sync(self, room_id: int, data: RoomPatch) -> Room:
        room = self._get_or_404(room_id)
        changes = data.model_dump(mode="json", exclude_unset=True, exclude_none=True)
        if "number" in changes:
            self._ensure_unique(changes["number"], room_id)
        for key, value in changes.items():
            setattr(room, key, value)
        return self._commit(lambda: self.repository.save(room))

    def _delete_sync(self, room_id: int) -> None:
        self.repository.delete(self._get_or_404(room_id))

    # Синхронная работа с БД выполняется в пуле потоков, чтобы не блокировать event loop;
    # после изменения кэш номера удаляется (инвалидация).
    async def replace(self, room_id: int, data: RoomCreate) -> Room:
        room = await run_in_threadpool(self._replace_sync, room_id, data)
        await self.cache.delete(self._key(room_id))
        return room

    async def patch(self, room_id: int, data: RoomPatch) -> Room:
        room = await run_in_threadpool(self._patch_sync, room_id, data)
        await self.cache.delete(self._key(room_id))
        return room

    async def delete(self, room_id: int) -> None:
        await run_in_threadpool(self._delete_sync, room_id)
        await self.cache.delete(self._key(room_id))

    def statistics(self) -> dict[str, Any]:
        stats = self.repository.statistics()
        total = stats["total"]
        stats["occupancy_percent"] = (round((1 - stats["available"] / total) * 100, 1)
                                      if total else 0.0)
        stats["average_price"] = round(stats["average_price"], 2)
        return stats

