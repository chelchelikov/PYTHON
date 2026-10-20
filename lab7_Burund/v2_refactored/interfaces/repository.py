"""Узкие интерфейсы хранилища (ISP)."""

from typing import Protocol, TypeVar

T = TypeVar("T")


class ReadableRepository(Protocol[T]):
    def get(self, entity_id: int) -> T:
        ...

    def get_all(self) -> list[T]:
        ...


class WritableRepository(Protocol[T]):
    def add(self, entity: T) -> None:
        ...

    def update(self, entity: T) -> None:
        ...

    def remove(self, entity_id: int) -> None:
        ...


class Repository(ReadableRepository[T], WritableRepository[T], Protocol[T]):
    def next_id(self) -> int:
        ...
