"""Интроспекция объектов."""

import inspect
from typing import Any


def inspect_object(obj: Any) -> None:
    cls = type(obj)
    print("=== ИНФОРМАЦИЯ ОБ ОБЪЕКТЕ ===")
    print("Тип:", cls.__name__)
    print("Иерархия классов:", " -> ".join(c.__name__ for c in cls.__mro__))
    if hasattr(obj, "id"):
        print("ID:", getattr(obj, "id"))
    print("Атрибуты:")
    for name, value in vars(obj).items():
        print(f"  {name} = {value!r:.60}")
    print("Методы:")
    for name, member in inspect.getmembers(obj, inspect.ismethod):
        if not name.startswith("_"):
            print(f"  {name}{inspect.signature(member)}")
    public = [name for name in dir(obj) if not name.startswith("_")]
    print("Все публичные имена (dir):", ", ".join(public))


def is_subclass_report(cls: type, base: type) -> str:
    return f"{cls.__name__} является подклассом {base.__name__}: {issubclass(cls, base)}"
