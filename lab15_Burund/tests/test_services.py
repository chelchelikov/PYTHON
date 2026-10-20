import pytest

from app.services import CategoryService, ConflictError, DishService, OrderService, ValidationError


def test_dish_service_partial_update(session):
    dish = DishService(session).update(3, {"price": "370"}, partial=True)
    assert dish.price == 370 and dish.name == "Борщ"


def test_category_delete_rules(session):
    service = CategoryService(session)
    with pytest.raises(ConflictError):
        service.delete(1)
    category = service.create({"name": "Завтраки"})
    service.delete(category.id)


def test_order_validation(session):
    service = OrderService(session)
    with pytest.raises(ValidationError):
        service.create("", 1, {1: 1})
    with pytest.raises(ValidationError):
        service.create("Гость", 1, {})
    with pytest.raises(ValidationError):
        service.change_status(1, "flying")
