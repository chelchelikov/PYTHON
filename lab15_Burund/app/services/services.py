"""Бизнес-логика ресторана. Сервисы не знают о Flask, HTML и JSON."""

import logging
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, Dish, Order, OrderItem, OrderStatus
from app.repositories import CategoryRepository, DishRepository, OrderRepository

log = logging.getLogger("restaurant.services")

TRANSITIONS = {
    OrderStatus.NEW: {OrderStatus.COOKING, OrderStatus.CANCELLED},
    OrderStatus.COOKING: {OrderStatus.SERVED, OrderStatus.CANCELLED},
    OrderStatus.SERVED: {OrderStatus.PAID},
    OrderStatus.PAID: set(),
    OrderStatus.CANCELLED: set(),
}


class ServiceError(Exception):
    status_code = 400


class ValidationError(ServiceError):
    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    status_code = 409


def _text(data: dict, key: str, label: str, required: bool = True, max_len: int = 100) -> str:
    value = str(data.get(key) or "").strip()
    if required and not value:
        raise ValidationError(f"Поле «{label}» обязательно")
    if len(value) > max_len:
        raise ValidationError(f"Поле «{label}» длиннее {max_len} символов")
    return value


def _number(data: dict, key: str, label: str, cast=float, minimum: float = 0) -> Any:
    try:
        value = cast(str(data.get(key)).replace(",", "."))
    except (TypeError, ValueError):
        raise ValidationError(f"Поле «{label}» должно быть числом") from None
    if value <= minimum:
        raise ValidationError(f"Поле «{label}» должно быть больше {minimum}")
    return value


def _flag(data: dict, key: str) -> bool:
    value = data.get(key)
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "on", "yes", "да")


class BaseService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise ConflictError("Конфликт данных: запись уже существует или используется") from None


class CategoryService(BaseService):
    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.repo = CategoryRepository(session)

    def list_all(self) -> list[Category]:
        return self.repo.all()

    def get(self, category_id: int) -> Category:
        category = self.repo.get(category_id)
        if category is None:
            raise NotFoundError(f"Категория #{category_id} не найдена")
        return category

    def create(self, data: dict) -> Category:
        name = _text(data, "name", "Название", max_len=50)
        if self.repo.get_by_name(name):
            raise ConflictError(f"Категория «{name}» уже существует")
        category = self.repo.add(Category(name=name,
                                          description=_text(data, "description", "Описание",
                                                            required=False, max_len=500)))
        self._commit()
        log.info("Создана категория %s", name)
        return category

    def delete(self, category_id: int) -> None:
        category = self.get(category_id)
        if category.dishes:
            raise ConflictError(f"В категории «{category.name}» есть блюда — удалить нельзя")
        self.repo.delete(category)
        self._commit()
        log.info("Удалена категория %s", category.name)


class DishService(BaseService):
    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.repo = DishRepository(session)
        self.categories = CategoryRepository(session)

    def list_all(self, filters: dict[str, Any] | None = None, sort: str = "name") -> list[Dish]:
        return self.repo.find(filters or {}, sort)

    def get(self, dish_id: int) -> Dish:
        dish = self.repo.get(dish_id)
        if dish is None:
            raise NotFoundError(f"Блюдо #{dish_id} не найдено")
        return dish

    def _validated(self, data: dict, partial_from: Dish | None = None) -> dict[str, Any]:
        if partial_from is not None:
            data = {**self._as_form(partial_from), **data}
        fields = {
            "name": _text(data, "name", "Название"),
            "description": _text(data, "description", "Описание", required=False, max_len=1000),
            "price": round(_number(data, "price", "Цена"), 2),
            "weight_g": _number(data, "weight_g", "Вес", int),
            "is_available": _flag(data, "is_available"),
            "is_vegetarian": _flag(data, "is_vegetarian"),
            "category_id": _number(data, "category_id", "Категория", int),
        }
        if self.categories.get(fields["category_id"]) is None:
            raise ValidationError(f"Категория #{fields['category_id']} не существует")
        return fields

    @staticmethod
    def _as_form(dish: Dish) -> dict[str, Any]:
        return {"name": dish.name, "description": dish.description, "price": dish.price,
                "weight_g": dish.weight_g, "is_available": dish.is_available,
                "is_vegetarian": dish.is_vegetarian, "category_id": dish.category_id}

    def _check_unique(self, name: str, dish_id: int | None = None) -> None:
        existing = self.repo.get_by_name(name)
        if existing is not None and existing.id != dish_id:
            raise ConflictError(f"Блюдо «{name}» уже есть в меню")

    def create(self, data: dict) -> Dish:
        fields = self._validated(data)
        self._check_unique(fields["name"])
        dish = self.repo.add(Dish(**fields))
        self._commit()
        log.info("Создано блюдо #%s %s", dish.id, dish.name)
        return dish

    def update(self, dish_id: int, data: dict, partial: bool = False) -> Dish:
        dish = self.get(dish_id)
        fields = self._validated(data, partial_from=dish if partial else None)
        self._check_unique(fields["name"], dish_id)
        for key, value in fields.items():
            setattr(dish, key, value)
        self._commit()
        log.info("Изменено блюдо #%s", dish_id)
        return dish

    def delete(self, dish_id: int) -> None:
        dish = self.get(dish_id)
        if dish.items:
            raise ConflictError(f"Блюдо «{dish.name}» есть в заказах — снимите его с продажи "
                                f"вместо удаления")
        self.repo.delete(dish)
        self._commit()
        log.info("Удалено блюдо #%s %s", dish_id, dish.name)

    def popular(self) -> list[tuple[Dish, int]]:
        return self.repo.popular()


class OrderService(BaseService):
    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.repo = OrderRepository(session)
        self.dishes = DishRepository(session)

    def list_all(self, status: str | None = None, search: str | None = None) -> list[Order]:
        return self.repo.find(self.parse_status(status) if status else None, search)

    def get(self, order_id: int) -> Order:
        order = self.repo.get(order_id)
        if order is None:
            raise NotFoundError(f"Заказ #{order_id} не найден")
        return order

    @staticmethod
    def parse_status(value: str) -> OrderStatus:
        try:
            return OrderStatus[value.upper()]
        except KeyError:
            raise ValidationError(f"Неизвестный статус заказа: {value}") from None

    def create(self, customer_name: str, table_number: Any, items: dict[int, int],
               comment: str = "") -> Order:
        """Оформление заказа из нескольких блюд одной транзакцией."""
        data = {"customer_name": customer_name, "table_number": table_number}
        name = _text(data, "customer_name", "Имя гостя")
        table = _number(data, "table_number", "Номер стола", int)
        items = {dish_id: qty for dish_id, qty in items.items() if qty}
        if not items:
            raise ValidationError("Выберите хотя бы одно блюдо")
        if any(qty < 0 for qty in items.values()):
            raise ValidationError("Количество не может быть отрицательным")
        dishes = self.dishes.get_many(list(items))
        order = Order(customer_name=name, table_number=table, comment=comment.strip())
        for dish_id, quantity in items.items():
            dish = dishes.get(dish_id)
            if dish is None:
                raise NotFoundError(f"Блюдо #{dish_id} не найдено")
            if not dish.is_available:
                raise ConflictError(f"Блюдо «{dish.name}» сейчас недоступно")
            order.items.append(OrderItem(dish=dish, quantity=quantity, price=dish.price))
        self.repo.add(order)
        self._commit()
        log.info("Оформлен заказ #%s на %.2f ₽", order.id, order.total)
        return order

    def change_status(self, order_id: int, status: str) -> Order:
        order = self.get(order_id)
        new_status = self.parse_status(status)
        if new_status not in TRANSITIONS[order.status]:
            raise ConflictError(f"Заказ #{order_id}: нельзя перейти из «{order.status.value}» "
                                f"в «{new_status.value}»")
        order.status = new_status
        self._commit()
        log.info("Заказ #%s: статус %s", order_id, new_status.value)
        return order

    def next_statuses(self, order: Order) -> list[OrderStatus]:
        return sorted(TRANSITIONS[order.status], key=lambda s: list(OrderStatus).index(s))
