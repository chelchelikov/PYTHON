import json
import os
from typing import Any, Callable, Generic, TypeVar

from repositories.memory_repository import InMemoryRepository

T = TypeVar("T")


class JsonFileRepository(Generic[T]):
    """Хранилище в JSON-файле. Взаимозаменяемо с InMemoryRepository (LSP)."""

    def __init__(self, path: str, to_dict: Callable[[T], dict[str, Any]],
                 from_dict: Callable[[dict[str, Any]], T]) -> None:
        self._path = path
        self._to_dict = to_dict
        self._cache: InMemoryRepository[T] = InMemoryRepository()
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                for item in json.load(file):
                    self._cache.add(from_dict(item))

    def _flush(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as file:
            json.dump([self._to_dict(e) for e in self._cache.get_all()], file,
                      ensure_ascii=False, indent=2)

    def add(self, entity: T) -> None:
        self._cache.add(entity)
        self._flush()

    def update(self, entity: T) -> None:
        self._cache.update(entity)
        self._flush()

    def remove(self, entity_id: int) -> None:
        self._cache.remove(entity_id)
        self._flush()

    def get(self, entity_id: int) -> T:
        return self._cache.get(entity_id)

    def get_all(self) -> list[T]:
        return self._cache.get_all()

    def next_id(self) -> int:
        return self._cache.next_id()
