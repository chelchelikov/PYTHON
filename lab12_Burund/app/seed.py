"""Заполнение базы тестовыми данными."""

from sqlalchemy.orm import sessionmaker

from app.models import DishCategory, OrderStatus
from app.services import CustomerService, DishService, OrderService

DISHES = [
    ("Цезарь с курицей", DishCategory.SALAD, 450, 250, 20),
    ("Греческий салат", DishCategory.SALAD, 390, 230, 15),
    ("Борщ", DishCategory.SOUP, 350, 300, 25),
    ("Том ям", DishCategory.SOUP, 520, 350, 10),
    ("Стейк рибай", DishCategory.MAIN, 1890, 300, 8),
    ("Паста карбонара", DishCategory.MAIN, 590, 320, 18),
    ("Лосось на гриле", DishCategory.MAIN, 1250, 250, 6),
    ("Чизкейк", DishCategory.DESSERT, 380, 150, 12),
    ("Тирамису", DishCategory.DESSERT, 420, 140, 2),
    ("Морс клюквенный", DishCategory.DRINK, 190, 400, 50),
]

CUSTOMERS = [
    ("Иванов Иван", "+79001112233", "ivanov@mail.ru"),
    ("Петрова Анна", "+79002223344", "petrova@mail.ru"),
    ("Сидоров Пётр", "+79003334455", None),
    ("Бурунд", "+79004445566", "burund@mail.ru"),
    ("Кузнецова Мария", "+79005556677", "kuz@mail.ru"),
]


def seed(session_factory: sessionmaker) -> None:
    dishes = DishService(session_factory)
    customers = CustomerService(session_factory)
    orders = OrderService(session_factory)
    dish_ids = [dishes.create(*data).id for data in DISHES]
    customer_ids = [customers.create(*data).id for data in CUSTOMERS]

    first = orders.create_order(customer_ids[0], 3, {dish_ids[0]: 1, dish_ids[4]: 1,
                                                     dish_ids[9]: 2})
    orders.change_status(first.id, OrderStatus.COOKING)
    orders.change_status(first.id, OrderStatus.SERVED)
    orders.change_status(first.id, OrderStatus.PAID)
    orders.create_order(customer_ids[1], 5, {dish_ids[2]: 2, dish_ids[7]: 2})
    orders.create_order(customer_ids[3], 1, {dish_ids[5]: 1, dish_ids[3]: 1, dish_ids[8]: 1})
    cancelled = orders.create_order(customer_ids[0], 2, {dish_ids[6]: 2})
    orders.cancel_order(cancelled.id)
