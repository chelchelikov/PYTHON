"""Репозитории: доступ к данным через SQLAlchemy ORM (без ручного SQL)."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.exceptions import NotFoundError
from app.models import Customer, Dish, DishCategory, Order, OrderItem, OrderStatus

T = TypeVar("T")


class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, **fields: Any) -> T:
        entity = self.model(**fields)
        self.session.add(entity)
        self.session.flush()  # получить id, но не фиксировать транзакцию
        return entity

    def get_by_id(self, entity_id: int) -> T:
        entity = self.session.get(self.model, entity_id)
        if entity is None:
            raise NotFoundError(f"{self.model.__name__} с id={entity_id} не найден")
        return entity

    def get_all(self) -> Sequence[T]:
        return self.session.scalars(select(self.model).order_by(self.model.id)).all()

    def update(self, entity_id: int, **fields: Any) -> T:
        entity = self.get_by_id(entity_id)
        for key, value in fields.items():
            setattr(entity, key, value)
        self.session.flush()
        return entity

    def delete(self, entity_id: int) -> None:
        self.session.delete(self.get_by_id(entity_id))
        self.session.flush()


class CustomerRepository(BaseRepository[Customer]):
    model = Customer

    def search(self, text: str) -> Sequence[Customer]:
        pattern = f"%{text}%"
        stmt = (select(Customer)
                .where(or_(Customer.name.ilike(pattern), Customer.phone.like(pattern)))
                .order_by(Customer.name))
        return self.session.scalars(stmt).all()

    def get_with_orders(self, customer_id: int) -> Customer:
        stmt = (select(Customer).where(Customer.id == customer_id)
                .options(selectinload(Customer.orders).selectinload(Order.items)
                         .selectinload(OrderItem.dish)))
        customer = self.session.scalars(stmt).first()
        if customer is None:
            raise NotFoundError(f"Customer с id={customer_id} не найден")
        return customer


SORT_FIELDS = {"name": Dish.name, "price": Dish.price, "weight": Dish.weight_g,
               "portions": Dish.portions_left}


class DishRepository(BaseRepository[Dish]):
    model = Dish

    def find(self, category: DishCategory | None = None, min_price: Decimal | None = None,
             max_price: Decimal | None = None, only_available: bool = False,
             sort: str = "name", descending: bool = False) -> Sequence[Dish]:
        conditions = []
        if category is not None:
            conditions.append(Dish.category == category)
        if min_price is not None:
            conditions.append(Dish.price >= min_price)
        if max_price is not None:
            conditions.append(Dish.price <= max_price)
        if only_available:
            conditions.append(and_(Dish.is_available.is_(True), Dish.portions_left > 0))
        column = SORT_FIELDS[sort]
        stmt = (select(Dish).where(*conditions)
                .order_by(column.desc() if descending else column.asc(), Dish.id))
        return self.session.scalars(stmt).all()

    def search(self, text: str) -> Sequence[Dish]:
        stmt = select(Dish).where(Dish.name.ilike(f"%{text}%")).order_by(Dish.name)
        return self.session.scalars(stmt).all()

    def get_many_for_update(self, dish_ids: list[int]) -> dict[int, Dish]:
        # FOR UPDATE блокирует строки блюд до конца транзакции (в PostgreSQL)
        stmt = select(Dish).where(Dish.id.in_(dish_ids)).with_for_update()
        return {dish.id: dish for dish in self.session.scalars(stmt)}


class OrderRepository(BaseRepository[Order]):
    model = Order

    def _with_items(self):
        return (select(Order)
                .options(selectinload(Order.items).selectinload(OrderItem.dish),
                         selectinload(Order.customer)))

    def get_full(self, order_id: int) -> Order:
        order = self.session.scalars(self._with_items().where(Order.id == order_id)).first()
        if order is None:
            raise NotFoundError(f"Order с id={order_id} не найден")
        return order

    def find(self, status: OrderStatus | None = None, min_total: Decimal | None = None,
             created_after: datetime | None = None, customer_id: int | None = None,
             sort: str = "created", descending: bool = True) -> Sequence[Order]:
        conditions = []
        if status is not None:
            conditions.append(Order.status == status)
        if min_total is not None:
            conditions.append(Order.total >= min_total)
        if created_after is not None:
            conditions.append(Order.created_at >= created_after)
        if customer_id is not None:
            conditions.append(Order.customer_id == customer_id)
        column = Order.total if sort == "total" else Order.created_at
        stmt = (self._with_items().where(*conditions)
                .order_by(column.desc() if descending else column.asc(), Order.id))
        return self.session.scalars(stmt).all()

    def statistics(self) -> dict[str, Any]:
        paid = Order.status != OrderStatus.CANCELLED
        row = self.session.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0),
                   func.avg(Order.total), func.min(Order.total), func.max(Order.total))
            .where(paid)).one()
        popular = self.session.execute(
            select(Dish.name, func.sum(OrderItem.quantity).label("qty"))
            .join(OrderItem.dish).join(OrderItem.order).where(paid)
            .group_by(Dish.name).order_by(func.sum(OrderItem.quantity).desc()).limit(3)).all()
        by_status = self.session.execute(
            select(Order.status, func.count(Order.id)).group_by(Order.status)).all()
        return {
            "orders": row[0],
            "revenue": Decimal(row[1]),
            "average": Decimal(row[2] or 0).quantize(Decimal("0.01")),
            "min": row[3] or Decimal(0),
            "max": row[4] or Decimal(0),
            "popular_dishes": [(name, int(qty)) for name, qty in popular],
            "by_status": {status.value: count for status, count in by_status},
        }
