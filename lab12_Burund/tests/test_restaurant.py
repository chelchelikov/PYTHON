from decimal import Decimal

import pytest

from app.exceptions import DuplicateError, NotFoundError, OrderError, ValidationError
from app.models import DishCategory, OrderStatus
from app.services import CustomerService, DishService, OrderService


@pytest.fixture
def dishes(session_factory):
    return DishService(session_factory)


@pytest.fixture
def customers(session_factory):
    return CustomerService(session_factory)


@pytest.fixture
def orders(session_factory):
    return OrderService(session_factory)


# --- Repository / CRUD ---

def test_create_and_get_dish(dishes):
    dish = dishes.create("Окрошка", "суп", "330.5", 300, 10)
    loaded = dishes.get(dish.id)
    assert (loaded.name, loaded.category, loaded.price) == ("Окрошка", DishCategory.SOUP,
                                                            Decimal("330.50"))


def test_update_and_delete_dish(dishes):
    dish = dishes.create("Компот", DishCategory.DRINK, 150, 300)
    assert dishes.update(dish.id, price=170).price == Decimal("170.00")
    dishes.delete(dish.id)
    with pytest.raises(NotFoundError):
        dishes.get(dish.id)


def test_duplicate_and_validation(dishes, customers):
    with pytest.raises(DuplicateError):
        dishes.create("Борщ", DishCategory.SOUP, 300, 300)
    with pytest.raises(DuplicateError):
        customers.create("Двойник", "+79001112233")
    with pytest.raises(ValidationError):
        dishes.create("Вода", DishCategory.DRINK, -10, 500)


def test_filter_and_sort(dishes):
    mains = dishes.list_all(category=DishCategory.MAIN, sort="price", descending=True)
    assert [d.name for d in mains] == ["Стейк рибай", "Лосось на гриле", "Паста карбонара"]
    cheap = dishes.list_all(max_price=Decimal(400), min_price=Decimal(300), sort="price")
    assert [d.name for d in cheap] == ["Борщ", "Чизкейк", "Греческий салат"]


def test_search(dishes, customers):
    assert [d.name for d in dishes.search("салат")] == ["Греческий салат"]
    assert [c.name for c in customers.search("+7900222")] == ["Петрова Анна"]


def test_related_objects(customers):
    customer = customers.orders_of(1)
    assert len(customer.orders) == 2
    assert {o.status for o in customer.orders} == {OrderStatus.PAID, OrderStatus.CANCELLED}


def test_foreign_key_violation(customers):
    with pytest.raises(ValidationError):
        customers.delete(1)  # у клиента есть заказы


# --- Service / транзакции ---

def test_create_order_transaction(orders, dishes):
    before = dishes.get(5).portions_left
    order = orders.create_order(2, 7, {5: 2, 10: 1})
    assert order.total == Decimal("1890") * 2 + Decimal("190")
    assert len(order.items) == 2
    assert dishes.get(5).portions_left == before - 2


def test_order_rollback_when_not_enough_portions(orders, dishes):
    steak_before = dishes.get(5).portions_left
    tiramisu_before = dishes.get(9).portions_left
    count_before = len(orders.list_all())
    with pytest.raises(OrderError):
        orders.create_order(2, 7, {5: 1, 9: tiramisu_before + 1})
    assert dishes.get(5).portions_left == steak_before  # изменения откатились
    assert len(orders.list_all()) == count_before


def test_order_errors(orders):
    with pytest.raises(NotFoundError):
        orders.create_order(999, 1, {1: 1})
    with pytest.raises(NotFoundError):
        orders.create_order(1, 1, {999: 1})
    with pytest.raises(ValidationError):
        orders.create_order(1, 1, {})


def test_cancel_returns_portions(orders, dishes):
    order = orders.create_order(3, 4, {1: 3})
    before = dishes.get(1).portions_left
    orders.cancel_order(order.id)
    assert dishes.get(1).portions_left == before + 3
    with pytest.raises(OrderError):
        orders.change_status(order.id, OrderStatus.COOKING)


def test_find_orders_multiple_conditions(orders):
    found = orders.list_all(status=OrderStatus.NEW, min_total=Decimal(1000), sort="total")
    assert [o.total for o in found] == [Decimal("1530.00"), Decimal("1460.00")]


def test_statistics(orders):
    stats = orders.statistics()
    assert stats["orders"] == 3
    assert stats["revenue"] == Decimal("2720") + Decimal("1460") + Decimal("1530")
    assert stats["by_status"]["отменён"] == 1
