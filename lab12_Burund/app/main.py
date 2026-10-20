"""Лабораторная работа №12. Вариант 5. Ресторан — SQLAlchemy ORM + PostgreSQL.

Запуск из папки lab12_Burund:  python -m app.main
"""

from datetime import datetime, timedelta
from decimal import Decimal

from app.database import create_db_engine, create_session_factory, init_db
from app.exceptions import RestaurantError
from app.models import Dish, DishCategory, Order, OrderStatus
from app.seed import seed
from app.services import CustomerService, DishService, OrderService


def read_int(prompt: str, allow_empty: bool = False) -> int | None:
    while True:
        text = input(prompt).strip()
        if allow_empty and not text:
            return None
        try:
            return int(text)
        except ValueError:
            print("Ошибка: введите целое число")


def read_decimal(prompt: str) -> Decimal | None:
    while True:
        text = input(prompt).strip().replace(",", ".")
        if not text:
            return None
        try:
            return Decimal(text)
        except ArithmeticError:
            print("Ошибка: введите число")


def choose_enum(enum_cls, prompt: str, allow_empty: bool = True):
    members = list(enum_cls)
    for index, member in enumerate(members, 1):
        print(f"  {index}. {member.value}")
    index = read_int(prompt, allow_empty)
    if index is None:
        return None
    if not 1 <= index <= len(members):
        raise RestaurantError("Нет такого варианта")
    return members[index - 1]


def print_dishes(dishes: list[Dish]) -> None:
    if not dishes:
        print("Ничего не найдено")
    for d in dishes:
        state = "" if d.is_available else " (недоступно)"
        print(f"  {d.id:<3} {d.name:<20} {d.category.value:<9} {d.price:>8} ₽ "
              f"{d.weight_g:>4} г  осталось {d.portions_left}{state}")


def print_order(order: Order, customer_name: str | None = None) -> None:
    print(f"  Заказ #{order.id} | {customer_name or order.customer.name} | стол {order.table_number} | "
          f"{order.created_at:%d.%m.%Y %H:%M} | {order.status.value} | {order.total} ₽")
    for item in order.items:
        print(f"      {item.dish.name:<20} × {item.quantity} по {item.price} ₽")


class ConsoleApp:
    MENU = """
===== РЕСТОРАН =====
1. Меню блюд (фильтрация и сортировка)
2. Найти блюдо по названию
3. Добавить блюдо
4. Изменить блюдо
5. Удалить блюдо
6. Клиенты / поиск клиента
7. Добавить клиента
8. Заказы клиента (связанные объекты)
9. Оформить заказ (транзакция)
10. Изменить статус заказа
11. Отменить заказ (транзакция)
12. Найти заказы (несколько условий)
13. Статистика (агрегаты)
0. Выход"""

    def __init__(self, session_factory) -> None:
        self.dishes = DishService(session_factory)
        self.customers = CustomerService(session_factory)
        self.orders = OrderService(session_factory)

    def menu_dishes(self) -> None:
        category = choose_enum(DishCategory, "Категория [Enter — все]: ")
        min_price = read_decimal("Цена от [Enter — пропустить]: ")
        max_price = read_decimal("Цена до [Enter — пропустить]: ")
        only_available = input("Только доступные? (д/н): ").strip().lower() == "д"
        sort = input("Сортировка (name / price / weight / portions) [name]: ").strip() or "name"
        if sort not in ("name", "price", "weight", "portions"):
            raise RestaurantError("Неизвестное поле сортировки")
        descending = input("По убыванию? (д/н): ").strip().lower() == "д"
        print_dishes(self.dishes.list_all(category=category, min_price=min_price,
                                      max_price=max_price, only_available=only_available,
                                      sort=sort, descending=descending))

    def add_dish(self) -> None:
        name = input("Название: ")
        category = choose_enum(DishCategory, "Категория: ", allow_empty=False)
        price = read_decimal("Цена: ")
        weight = read_int("Вес, г: ")
        portions = read_int("Порций в наличии: ")
        print_dishes([self.dishes.create(name, category, price, weight, portions)])

    def edit_dish(self) -> None:
        dish_id = read_int("id блюда: ")
        fields = {}
        price = read_decimal("Новая цена [Enter — без изменений]: ")
        if price is not None:
            fields["price"] = price
        portions = read_int("Порций в наличии [Enter — без изменений]: ", allow_empty=True)
        if portions is not None:
            fields["portions_left"] = portions
        available = input("Доступно? (д/н) [Enter — без изменений]: ").strip().lower()
        if available in ("д", "н"):
            fields["is_available"] = available == "д"
        if not fields:
            print("Нет изменений")
            return
        print_dishes([self.dishes.update(dish_id, **fields)])

    def customers_menu(self) -> None:
        text = input("Поиск (имя или телефон) [Enter — все]: ").strip()
        customers = self.customers.search(text) if text else self.customers.list_all()
        for c in customers:
            print(f"  {c.id:<3} {c.name:<18} {c.phone:<14} {c.email or '—'}")

    def add_customer(self) -> None:
        customer = self.customers.create(input("Имя: "), input("Телефон: "),
                                         input("E-mail [Enter — нет]: ").strip() or None)
        print("Добавлен клиент:", customer)

    def customer_orders(self) -> None:
        customer = self.customers.orders_of(read_int("id клиента: "))
        print(f"Клиент {customer.name}, заказов: {len(customer.orders)}")
        for order in customer.orders:
            print_order(order, customer.name)

    def create_order(self) -> None:
        customer_id = read_int("id клиента: ")
        table = read_int("Номер стола: ")
        items: dict[int, int] = {}
        print("Вводите блюда; пустой id — закончить")
        while True:
            dish_id = read_int("  id блюда: ", allow_empty=True)
            if dish_id is None:
                break
            items[dish_id] = items.get(dish_id, 0) + read_int("  количество: ")
        print_order(self.orders.create_order(customer_id, table, items))

    def change_status(self) -> None:
        order_id = read_int("id заказа: ")
        status = choose_enum(OrderStatus, "Новый статус: ", allow_empty=False)
        print_order(self.orders.change_status(order_id, status))

    def find_orders(self) -> None:
        status = choose_enum(OrderStatus, "Статус [Enter — любой]: ")
        min_total = read_decimal("Сумма от [Enter — любая]: ")
        days = read_int("За последние N дней [Enter — за всё время]: ", allow_empty=True)
        created_after = datetime.now() - timedelta(days=days) if days else None
        sort = "total" if input("Сортировать по сумме? (д/н): ").strip() == "д" else "created"
        orders = self.orders.list_all(status=status, min_total=min_total,
                                  created_after=created_after, sort=sort)
        for order in orders:
            print_order(order)
        if not orders:
            print("Заказы не найдены")

    def statistics(self) -> None:
        s = self.orders.statistics()
        print(f"Заказов (без отменённых): {s['orders']}, выручка {s['revenue']} ₽")
        print(f"Средний чек {s['average']} ₽, минимальный {s['min']} ₽, максимальный {s['max']} ₽")
        print("Популярные блюда:", ", ".join(f"{n} ({q})" for n, q in s["popular_dishes"]))
        print("По статусам:", s["by_status"])

    def run(self) -> None:
        actions = {
            "1": self.menu_dishes,
            "2": lambda: print_dishes(self.dishes.search(input("Название содержит: "))),
            "3": self.add_dish, "4": self.edit_dish,
            "5": lambda: self.dishes.delete(read_int("id блюда: ")),
            "6": self.customers_menu, "7": self.add_customer, "8": self.customer_orders,
            "9": self.create_order, "10": self.change_status,
            "11": lambda: print_order(self.orders.cancel_order(read_int("id заказа: "))),
            "12": self.find_orders, "13": self.statistics,
        }
        while True:
            print(self.MENU)
            choice = input("Выберите действие: ").strip()
            if choice == "0":
                return
            action = actions.get(choice)
            if action is None:
                print("Неизвестный пункт меню")
                continue
            try:
                action()
            except RestaurantError as error:
                print(f"Ошибка ({type(error).__name__}):", error)


def main() -> None:
    engine = create_db_engine()
    session_factory = create_session_factory(engine)
    reset = input("Пересоздать базу и заполнить тестовыми данными? (д/н): ").strip().lower()
    init_db(engine, drop=reset == "д")
    if reset == "д":
        seed(session_factory)
        print("База заполнена тестовыми данными")
    ConsoleApp(session_factory).run()


if __name__ == "__main__":
    main()
