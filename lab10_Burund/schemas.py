"""Проверка и преобразование входных данных."""

from typing import Any

from exceptions import ValidationError
from models import RoomStatus, RoomType

FIELDS = ("number", "room_type", "floor", "capacity", "price", "status")
REQUIRED = ("number", "room_type", "floor", "capacity", "price")
SORT_FIELDS = ("number", "floor", "capacity", "price")


def _enum(enum_cls, value: Any, field: str):
    try:
        return enum_cls(value)
    except ValueError:
        allowed = ", ".join(e.value for e in enum_cls)
        raise ValidationError(f"{field}: допустимые значения — {allowed}") from None


def _int(value: Any, field: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValidationError(f"{field} должно быть целым числом не меньше {minimum}")
    return value


def validate_room(data: Any, partial: bool = False) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError("Тело запроса должно быть JSON-объектом")
    unknown = set(data) - set(FIELDS)
    if unknown:
        raise ValidationError(f"Неизвестные поля: {', '.join(sorted(unknown))}")
    if not partial:
        missing = [f for f in REQUIRED if f not in data]
        if missing:
            raise ValidationError(f"Отсутствуют обязательные поля: {', '.join(missing)}")
    if partial and not data:
        raise ValidationError("Нет полей для изменения")

    result: dict[str, Any] = {}
    if "number" in data:
        if not isinstance(data["number"], str) or not data["number"].strip():
            raise ValidationError("number должно быть непустой строкой")
        result["number"] = data["number"].strip()
    if "room_type" in data:
        result["room_type"] = _enum(RoomType, data["room_type"], "room_type")
    if "status" in data:
        result["status"] = _enum(RoomStatus, data["status"], "status")
    if "floor" in data:
        result["floor"] = _int(data["floor"], "floor", 0)
    if "capacity" in data:
        result["capacity"] = _int(data["capacity"], "capacity", 1)
    if "price" in data:
        price = data["price"]
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
            raise ValidationError("price должно быть положительным числом")
        result["price"] = float(price)
    return result


def parse_query(args) -> dict[str, Any]:
    """Фильтры и сортировка из query-параметров."""
    query: dict[str, Any] = {}
    if "room_type" in args:
        query["room_type"] = _enum(RoomType, args["room_type"], "room_type")
    if "status" in args:
        query["status"] = _enum(RoomStatus, args["status"], "status")
    for name in ("min_price", "max_price"):
        if name in args:
            try:
                query[name] = float(args[name])
            except ValueError:
                raise ValidationError(f"{name} должно быть числом") from None
    for name in ("floor", "min_capacity", "guests"):
        if name in args:
            try:
                query[name] = int(args[name])
            except ValueError:
                raise ValidationError(f"{name} должно быть целым числом") from None
    sort = args.get("sort")
    if sort is not None and sort not in SORT_FIELDS:
        raise ValidationError(f"sort: допустимые поля — {', '.join(SORT_FIELDS)}")
    order = args.get("order", "asc")
    if order not in ("asc", "desc"):
        raise ValidationError("order: допустимо asc или desc")
    query["sort"] = sort
    query["descending"] = order == "desc"
    return query
