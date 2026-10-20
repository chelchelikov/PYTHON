"""Собственные декораторы."""

import time
from functools import wraps
from typing import Any, Callable

from exceptions import InvalidStatusError
from models import RoomStatus

LOG_ENABLED = True


def log_call(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if LOG_ENABLED:
            shown_args = [repr(a) for a in args[1:]] + [f"{k}={v!r}" for k, v in kwargs.items()]
            print(f"[LOG] вызван {func.__name__}({', '.join(shown_args)})")
        result = func(*args, **kwargs)
        if LOG_ENABLED:
            print(f"[LOG] {func.__name__} вернул: {result!r:.80}")
        return result
    return wrapper


def timed(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            print(f"[PERFORMANCE] {func.__name__}: {time.perf_counter() - start:.6f} sec")
    return wrapper


def require_status(*statuses: RoomStatus) -> Callable:
    """Разрешает вызов метода сервиса, только если номер находится в одном из состояний."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self: Any, room_id: int, *args: Any, **kwargs: Any) -> Any:
            room = self.get_room(room_id)
            if room.status not in statuses:
                allowed = ", ".join(s.value for s in statuses)
                raise InvalidStatusError(
                    f"Операция {func.__name__} недоступна: номер {room.name} "
                    f"«{room.status.value}», требуется: {allowed}")
            return func(self, room_id, *args, **kwargs)
        return wrapper
    return decorator


def limit_calls(max_calls: int) -> Callable:
    def decorator(func: Callable) -> Callable:
        calls = 0

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            nonlocal calls
            if calls >= max_calls:
                raise RuntimeError(f"{func.__name__}: превышен лимит вызовов ({max_calls})")
            calls += 1
            return func(*args, **kwargs)
        return wrapper
    return decorator
