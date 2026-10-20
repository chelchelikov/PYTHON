"""Сервисы: бизнес-логика и управление транзакциями."""

from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.exceptions import DuplicateError, NotFoundError, OrderError, ValidationError
from app.models import Customer, Dish, DishCategory, Order, OrderItem, OrderStatus
from app.repositories import CustomerRepository, DishRepository, OrderRepository

# Допустимые переходы статуса заказа
TRANSITIONS = {
    OrderStatus.NEW: {OrderStatus.COOKING, OrderStatus.CANCELLED},
    OrderStatus.COOKING: {OrderStatus.SERVED, OrderStatus.CANCELLED},
    OrderStatus.SERVED: {OrderStatus.PAID},
    OrderStatus.PAID: set(),
    OrderStatus.CANCELLED: set(),
}


def to_price(value: Any) -> Decimal:
    try:
        price = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValidationError(f"Некорректная цена: {value}") from None
    if price <= 0:
        raise ValidationError("Цена должна быть положительной")
    return price


class BaseService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Одна операция сервиса = одна транзакция: COMMIT при успехе, ROLLBACK при ошибке."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except IntegrityError as error:
            session.rollback()
            message = str(error.orig).lower()
            if "unique" in message or "duplicate" in message:
                raise DuplicateError("Запись с такими данными уже существует") from None
            if "foreign key" in message:
                raise ValidationError("Нарушение внешнего ключа: связанная запись "
                                      "не существует или используется") from None
            raise ValidationError(f"Нарушение ограничения целостности: {error.orig}") from None
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class CustomerService(BaseService):
    def create(self, name: str, phone: str, email: str | None = None) -> Customer:
        if not name.strip() or not phone.strip():
            raise ValidationError("Имя и телефон обязательны")
        if email and "@" not in email:
            raise ValidationError("Некорректный e-mail")
        with self.transaction() as session:
            return CustomerRepository(session).create(name=name.strip(), phone=phone.strip(),
                                                      email=email or None)

    def get(self, customer_id: int) -> Customer:
        with self.transaction() as session:
            return CustomerRepository(session).get_by_id(customer_id)

    def list_all(self) -> list[Customer]:
        with self.transaction() as session:
            return list(CustomerRepository(session).get_all())

    def search(self, text: str) -> list[Customer]:
        with self.transaction() as session:
            return list(CustomerRepository(session).search(text))

    def update(self, customer_id: int, **fields: Any) -> Customer:
        with self.transaction() as session:
            return CustomerRepository(session).update(customer_id, **fields)

    def delete(self, customer_id: int) -> None:
        with self.transaction() as session:
            customer = CustomerRepository(session).get_with_orders(customer_id)
            if customer.orders:
                raise ValidationError("У клиента есть заказы — удалить его нельзя")
            CustomerRepository(session).delete(customer_id)

    def orders_of(self, customer_id: int) -> Customer:
        """Связанные объекты: клиент со всеми заказами и позициями."""
        with self.transaction() as session:
            return CustomerRepository(session).get_with_orders(customer_id)


class DishService(BaseService):
    def create(self, name: str, category: DishCategory | str, price: Any, weight_g: int,
               portions_left: int = 20) -> Dish:
        if not name.strip():
            raise ValidationError("Название блюда обязательно")
        if isinstance(category, str):
            try:
                category = DishCategory(category)
            except ValueError:
                raise ValidationError(f"Неизвестная категория: {category}") from None
        if weight_g <= 0 or portions_left < 0:
            raise ValidationError("Вес должен быть положительным, остаток — неотрицательным")
        with self.transaction() as session:
            return DishRepository(session).create(name=name.strip(), category=category,
                                                  price=to_price(price), weight_g=weight_g,
                                                  portions_left=portions_left)

    def get(self, dish_id: int) -> Dish:
        with self.transaction() as session:
            return DishRepository(session).get_by_id(dish_id)

    def list_all(self, **filters: Any) -> list[Dish]:
        with self.transaction() as session:
            return list(DishRepository(session).find(**filters))

    def search(self, text: str) -> list[Dish]:
        with self.transaction() as session:
            return list(DishRepository(session).search(text))

    def update(self, dish_id: int, **fields: Any) -> Dish:
        if "price" in fields:
            fields["price"] = to_price(fields["price"])
        with self.transaction() as session:
            return DishRepository(session).update(dish_id, **fields)

    def delete(self, dish_id: int) -> None:
        with self.transaction() as session:
            DishRepository(session).delete(dish_id)


class OrderService(BaseService):
    def create_order(self, customer_id: int, table_number: int,
                     items: dict[int, int]) -> Order:
        """Создание заказа из нескольких блюд — атомарная операция.

        1) проверить клиента; 2) проверить наличие блюд и порций;
        3) уменьшить остатки; 4) создать заказ и позиции; 5) посчитать сумму; COMMIT.
        Любая ошибка — ROLLBACK, остатки блюд не меняются.
        """
        if not items:
            raise ValidationError("Заказ должен содержать хотя бы одно блюдо")
        if any(qty <= 0 for qty in items.values()):
            raise ValidationError("Количество порций должно быть положительным")
        if table_number <= 0:
            raise ValidationError("Номер стола должен быть положительным")
        with self.transaction() as session:
            CustomerRepository(session).get_by_id(customer_id)
            dishes = DishRepository(session).get_many_for_update(list(items))
            order = OrderRepository(session).create(customer_id=customer_id,
                                                    table_number=table_number)
            for dish_id, quantity in items.items():
                dish = dishes.get(dish_id)
                if dish is None:
                    raise NotFoundError(f"Блюдо с id={dish_id} не найдено")
                if not dish.is_available:
                    raise OrderError(f"Блюдо «{dish.name}» сейчас недоступно")
                if dish.portions_left < quantity:
                    raise OrderError(f"Блюдо «{dish.name}»: осталось {dish.portions_left} "
                                     f"порц., запрошено {quantity}")
                dish.portions_left -= quantity
                order.items.append(OrderItem(dish=dish, quantity=quantity, price=dish.price))
            order.total = order.calculate_total()
            session.flush()
            return OrderRepository(session).get_full(order.id)

    def cancel_order(self, order_id: int) -> Order:
        """Отмена заказа: статус + возврат порций на склад в одной транзакции."""
        with self.transaction() as session:
            order = OrderRepository(session).get_full(order_id)
            self._check_transition(order, OrderStatus.CANCELLED)
            for item in order.items:
                item.dish.portions_left += item.quantity
            order.status = OrderStatus.CANCELLED
            return order

    @staticmethod
    def _check_transition(order: Order, new_status: OrderStatus) -> None:
        if new_status not in TRANSITIONS[order.status]:
            raise OrderError(f"Заказ #{order.id}: нельзя перейти из «{order.status.value}» "
                             f"в «{new_status.value}»")

    def change_status(self, order_id: int, new_status: OrderStatus) -> Order:
        if new_status == OrderStatus.CANCELLED:
            return self.cancel_order(order_id)
        with self.transaction() as session:
            order = OrderRepository(session).get_full(order_id)
            self._check_transition(order, new_status)
            order.status = new_status
            return order

    def get(self, order_id: int) -> Order:
        with self.transaction() as session:
            return OrderRepository(session).get_full(order_id)

    def list_all(self, **filters: Any) -> list[Order]:
        with self.transaction() as session:
            return list(OrderRepository(session).find(**filters))

    def delete(self, order_id: int) -> None:
        with self.transaction() as session:
            order = OrderRepository(session).get_full(order_id)
            if order.status not in (OrderStatus.CANCELLED, OrderStatus.PAID):
                raise OrderError("Удалить можно только оплаченный или отменённый заказ")
            OrderRepository(session).delete(order_id)

    def statistics(self) -> dict[str, Any]:
        with self.transaction() as session:
            return OrderRepository(session).statistics()
