"""Разбор параметров запроса, общий для HTML- и API-маршрутов."""

from flask import request


def dish_filters() -> tuple[dict, str]:
    args = request.args
    filters = {
        "search": args.get("search", "").strip(),
        "category_id": args.get("category", type=int),
        "max_price": args.get("max_price", type=float),
        "vegetarian": args.get("vegetarian") in ("1", "on", "true"),
        "available": args.get("available") in ("1", "on", "true"),
    }
    return filters, args.get("sort", "name")


def order_items_from_form() -> dict[int, int]:
    items = {}
    for key, value in request.form.items():
        if key.startswith("qty_") and value.strip():
            try:
                items[int(key[4:])] = int(value)
            except ValueError:
                continue
    return items
