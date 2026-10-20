import json
import os
from dataclasses import asdict
from datetime import date
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

from repositories.memory_repository import InMemoryRepository

T = TypeVar("T")


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, date):
        return value.isoformat()
    return value


class FileRepository(Generic[T]):
    """JSON-хранилище с тем же интерфейсом, что и InMemoryRepository."""

    def __init__(self, path: str, from_dict: Callable[[dict], T]) -> None:
        self._path = path
        self._memory: InMemoryRepository[T] = InMemoryRepository()
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                for item in json.load(file):
                    self._memory.add(from_dict(item))

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        data = [{k: _encode(v) for k, v in asdict(e).items()} for e in self._memory.get_all()]
        with open(self._path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def add(self, entity: T) -> None:
        self._memory.add(entity)
        self._save()

    def get(self, entity_id: int) -> T:
        return self._memory.get(entity_id)

    def get_all(self) -> list[T]:
        return self._memory.get_all()

    def update(self, entity: T) -> None:
        self._memory.update(entity)
        self._save()

    def delete(self, entity_id: int) -> None:
        self._memory.delete(entity_id)
        self._save()

    def next_id(self) -> int:
        return self._memory.next_id()
