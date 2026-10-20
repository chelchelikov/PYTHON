"""Проверка и преобразование входных данных."""

from datetime import date
from typing import Any

from exceptions import ValidationError

ROOM_TYPES = ("standard", "deluxe", "suite", "family")
STATUSES = ("free", "booked", "occupied", "maintenance")
FIELDS = ("number", "room_type", "floor", "capacity", "price", "status", "amenities")
REQUIRED = ("number", "room_type", "floor", "capacity", "price")
SORT_FIELDS = ("number", "floor", "capacity", "price")


def _choice(value: Any, allowed: tuple, field: str) -> str:
    if value not in allowed:
        raise ValidationError(f"{field}: допустимые значения — {', '.join(allowed)}")
    return value


def _int(value: Any, field: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValidationError(f"{field} должно быть целым числом не меньше {minimum}")
    return value


def parse_date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field}: ожидается дата в формате ГГГГ-ММ-ДД") from None


def validate_room(data: Any, partial: bool = False) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError("Тело запроса должно быть JSON-объектом")
    unknown = set(data) - set(FIELDS)
    if unknown:
        raise ValidationError(f"Неизвестные поля: {', '.join(sorted(unknown))}")
    missing = [f for f in REQUIRED if f not in data]
    if not partial and missing:
        raise ValidationError(f"Отсутствуют обязательные поля: {', '.join(missing)}")
    if partial and not data:
        raise ValidationError("Нет полей для изменения")

    result: dict[str, Any] = {}
    if "number" in data:
        if not isinstance(data["number"], str) or not data["number"].strip():
            raise ValidationError("number должно быть непустой строкой")
        result["number"] = data["number"].strip()
    if "room_type" in data:
        result["room_type"] = _choice(data["room_type"], ROOM_TYPES, "room_type")
    if "status" in data:
        result["status"] = _choice(data["status"], STATUSES, "status")
    if "floor" in data:
        result["floor"] = _int(data["floor"], "floor", 0)
    if "capacity" in data:
        result["capacity"] = _int(data["capacity"], "capacity", 1)
    if "price" in data:
        price = data["price"]
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
            raise ValidationError("price должно быть положительным числом")
        result["price"] = float(price)
    if "amenities" in data:
        amenities = data["amenities"]
        if not isinstance(amenities, list) or not all(isinstance(a, str) and a.strip()
                                                      for a in amenities):
            raise ValidationError("amenities должно быть списком строк")
        result["amenities"] = sorted({a.strip() for a in amenities})
    return result


def parse_query(args) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if "room_type" in args:
        query["room_type"] = _choice(args["room_type"], ROOM_TYPES, "room_type")
    if "status" in args:
        query["status"] = _choice(args["status"], STATUSES, "status")
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
    if "check_in" in args or "check_out" in args:
        query["check_in"] = parse_date(args.get("check_in"), "check_in")
        query["check_out"] = parse_date(args.get("check_out"), "check_out")
        if query["check_out"] <= query["check_in"]:
            raise ValidationError("check_out должна быть позже check_in")
    if "amenity" in args:
        query["amenity"] = args["amenity"]
    sort = args.get("sort")
    if sort is not None and sort not in SORT_FIELDS:
        raise ValidationError(f"sort: допустимые поля — {', '.join(SORT_FIELDS)}")
    order = args.get("order", "asc")
    if order not in ("asc", "desc"):
        raise ValidationError("order: допустимо asc или desc")
    query["sort"] = sort
    query["descending"] = order == "desc"
    return query


def validate_booking(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError("Тело запроса должно быть JSON-объектом")
    guest = data.get("guest")
    if (not isinstance(guest, dict) or not str(guest.get("name", "")).strip()
            or "@" not in str(guest.get("email", ""))):
        raise ValidationError("guest: требуются name и корректный email")
    check_in = parse_date(data.get("check_in"), "check_in")
    check_out = parse_date(data.get("check_out"), "check_out")
    if check_out <= check_in:
        raise ValidationError("check_out должна быть позже check_in")
    rooms = data.get("rooms")
    if not isinstance(rooms, list) or not rooms:
        raise ValidationError("rooms: требуется непустой список номеров")
    items = []
    for item in rooms:
        if not isinstance(item, dict):
            raise ValidationError("rooms: каждый элемент — объект {room_id, guests}")
        items.append({"room_id": _int(item.get("room_id"), "room_id", 1),
                      "guests": _int(item.get("guests", 1), "guests", 1)})
    if len({i["room_id"] for i in items}) != len(items):
        raise ValidationError("rooms: номер указан несколько раз")
    return {"guest": {"name": guest["name"].strip(), "email": guest["email"].strip(),
                      "phone": guest.get("phone")},
            "check_in": check_in, "check_out": check_out, "rooms": items}
