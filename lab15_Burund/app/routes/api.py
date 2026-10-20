from flask import Blueprint, jsonify, request

from app.database import get_session
from app.routes.forms import dish_filters
from app.services import (CategoryService, DishService, OrderService, ValidationError)

api = Blueprint("api", __name__)


def body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Ожидается JSON-объект в теле запроса")
    return data


@api.get("/dishes")
def list_dishes():
    filters, sort = dish_filters()
    return jsonify([d.to_dict() for d in DishService(get_session()).list_all(filters, sort)])


@api.get("/dishes/<int:dish_id>")
def get_dish(dish_id: int):
    return jsonify(DishService(get_session()).get(dish_id).to_dict())


@api.post("/dishes")
def create_dish():
    dish = DishService(get_session()).create(body())
    return jsonify(dish.to_dict()), 201, {"Location": f"/api/dishes/{dish.id}"}


@api.put("/dishes/<int:dish_id>")
def replace_dish(dish_id: int):
    return jsonify(DishService(get_session()).update(dish_id, body()).to_dict())


@api.patch("/dishes/<int:dish_id>")
def patch_dish(dish_id: int):
    return jsonify(DishService(get_session()).update(dish_id, body(), partial=True).to_dict())


@api.delete("/dishes/<int:dish_id>")
def delete_dish(dish_id: int):
    DishService(get_session()).delete(dish_id)
    return "", 204


@api.get("/categories")
def list_categories():
    return jsonify([c.to_dict() for c in CategoryService(get_session()).list_all()])


@api.get("/categories/<int:category_id>/dishes")
def category_dishes(category_id: int):
    category = CategoryService(get_session()).get(category_id)
    return jsonify([d.to_dict() for d in category.dishes])


@api.post("/categories")
def create_category():
    category = CategoryService(get_session()).create(body())
    return jsonify(category.to_dict()), 201


@api.get("/orders")
def list_orders():
    orders = OrderService(get_session()).list_all(request.args.get("status"),
                                                  request.args.get("search"))
    return jsonify([o.to_dict() for o in orders])


@api.get("/orders/<int:order_id>")
def get_order(order_id: int):
    return jsonify(OrderService(get_session()).get(order_id).to_dict())


@api.post("/orders")
def create_order():
    data = body()
    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        raise ValidationError("items: ожидается список {dish_id, quantity}")
    items: dict[int, int] = {}
    for item in raw_items:
        try:
            items[int(item["dish_id"])] = items.get(int(item["dish_id"]), 0) + int(item["quantity"])
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Каждая позиция: {\"dish_id\": int, \"quantity\": int}") from None
    order = OrderService(get_session()).create(data.get("customer_name", ""),
                                               data.get("table_number"), items,
                                               str(data.get("comment", "")))
    return jsonify(order.to_dict()), 201, {"Location": f"/api/orders/{order.id}"}


@api.patch("/orders/<int:order_id>")
def update_order_status(order_id: int):
    status = body().get("status")
    if not status:
        raise ValidationError("Поле status обязательно")
    return jsonify(OrderService(get_session()).change_status(order_id, status).to_dict())
