"""Контекстные менеджеры."""

import copy
import time
from contextlib import contextmanager
from typing import Iterator


class HotelTransaction:
    """Транзакционный режим: при ошибке состояние гостиницы откатывается."""

    def __init__(self, hotel: "object", title: str) -> None:
        self.hotel = hotel
        self.title = title
        self._snapshot: dict | None = None

    def __enter__(self) -> "object":
        print(f"[TRANSACTION] начало: {self.title}")
        self._snapshot = copy.deepcopy(self.hotel.__dict__)
        return self.hotel

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if exc_type is None:
            print(f"[TRANSACTION] подтверждено: {self.title}")
            return False
        self.hotel.__dict__.clear()
        self.hotel.__dict__.update(self._snapshot)
        print(f"[TRANSACTION] откат «{self.title}»: {exc_value}")
        return False


@contextmanager
def measure(block_name: str) -> Iterator[None]:
    start = time.perf_counter()
    print(f"[BLOCK] {block_name}: начало")
    try:
        yield
    finally:
        print(f"[BLOCK] {block_name}: завершено за {time.perf_counter() - start:.6f} sec")
