from typing import Generic, TypeVar

from models.entities import HotelError

T = TypeVar("T")


class InMemoryRepository(Generic[T]):
    def __init__(self) -> None:
        self._items: dict[int, T] = {}

    def add(self, entity: T) -> None:
        if entity.id in self._items:
            raise HotelError(f"Объект с id={entity.id} уже существует")
        self._items[entity.id] = entity

    def get(self, entity_id: int) -> T:
        if entity_id not in self._items:
            raise HotelError(f"Объект с id={entity_id} не найден")
        return self._items[entity_id]

    def get_all(self) -> list[T]:
        return list(self._items.values())

    def update(self, entity: T) -> None:
        self.get(entity.id)
        self._items[entity.id] = entity

    def delete(self, entity_id: int) -> None:
        self.get(entity_id)
        del self._items[entity_id]

    def next_id(self) -> int:
        return max(self._items, default=0) + 1
