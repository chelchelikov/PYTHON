"""Доступ к данным через SQLAlchemy. Репозитории не фиксируют транзакции — это делает сервис."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Delivery,
    DeliveryStatus,
    Dish,
    Order,
    OrderItem,
    OrderStatus,
    OutboxEvent,
    User,
)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def by_email(self, email: str) -> User | None:
        return self.session.scalars(select(User).where(User.email == email.lower())).first()

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user


DISH_SORT = {"name": Dish.name.asc(), "price": Dish.price.asc(), "-price": Dish.price.desc()}


class DishRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(
        self, filters: dict[str, Any], sort: str, limit: int, offset: int
    ) -> tuple[int, list[Dish]]:
        conditions = []
        if filters.get("q"):
            pattern = f"%{filters['q'].lower()}%"
            conditions.append(
                or_(func.lower(Dish.name).like(pattern), func.lower(Dish.description).like(pattern))
            )
        if filters.get("category"):
            conditions.append(Dish.category == filters["category"])
        if filters.get("max_price") is not None:
            conditions.append(Dish.price <= filters["max_price"])
        if filters.get("available_only"):
            conditions.append(Dish.is_available.is_(True))
            conditions.append(Dish.portions_available > 0)
        total = self.session.scalar(select(func.count(Dish.id)).where(*conditions))
        stmt = (
            select(Dish)
            .where(*conditions)
            .order_by(DISH_SORT[sort], Dish.id)
            .limit(limit)
            .offset(offset)
        )
        return total, list(self.session.scalars(stmt))

    def get(self, dish_id: int) -> Dish | None:
        return self.session.get(Dish, dish_id)

    def by_name(self, name: str) -> Dish | None:
        return self.session.scalars(select(Dish).where(Dish.name == name)).first()

    def lock_many(self, dish_ids: list[int]) -> dict[int, Dish]:
        # SELECT ... FOR UPDATE: два заказа не спишут одни и те же порции одновременно
        stmt = select(Dish).where(Dish.id.in_(dish_ids)).with_for_update()
        return {dish.id: dish for dish in self.session.scalars(stmt)}

    def add(self, dish: Dish) -> Dish:
        self.session.add(dish)
        self.session.flush()
        return dish

    def delete(self, dish: Dish) -> None:
        self.session.delete(dish)
        self.session.flush()

    def is_ordered(self, dish_id: int) -> bool:
        return (
            self.session.scalar(
                select(func.count(OrderItem.id)).where(OrderItem.dish_id == dish_id)
            )
            > 0
        )

    def count(self) -> int:
        return self.session.scalar(select(func.count(Dish.id)))


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, order_id: int) -> Order | None:
        return self.session.get(Order, order_id)

    def find(
        self,
        user_id: int | None,
        status: OrderStatus | None,
        newest_first: bool,
        limit: int,
        offset: int,
    ) -> list[Order]:
        stmt = select(Order)
        if user_id is not None:
            stmt = stmt.where(Order.user_id == user_id)
        if status is not None:
            stmt = stmt.where(Order.status == status)
        order = Order.created_at.desc() if newest_first else Order.created_at.asc()
        return list(
            self.session.scalars(
                stmt.order_by(order, Order.id.desc() if newest_first else Order.id)
                .limit(limit)
                .offset(offset)
            )
        )

    def add(self, order: Order) -> Order:
        self.session.add(order)
        self.session.flush()
        return order

    def delete(self, order: Order) -> None:
        self.session.delete(order)
        self.session.flush()

    def statistics(self) -> dict[str, Any]:
        not_cancelled = Order.status != OrderStatus.CANCELLED
        row = self.session.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.total), 0),
                func.coalesce(func.avg(Order.total), 0),
            ).where(not_cancelled)
        ).one()
        popular = self.session.execute(
            select(Dish.name, func.sum(OrderItem.quantity))
            .join(OrderItem, OrderItem.dish_id == Dish.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(not_cancelled)
            .group_by(Dish.name)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(5)
        ).all()
        by_status = self.session.execute(
            select(Order.status, func.count(Order.id)).group_by(Order.status)
        ).all()
        return {
            "orders": row[0],
            "revenue": round(float(row[1]), 2),
            "average_check": round(float(row[2]), 2),
            "popular_dishes": [{"name": n, "quantity": int(q)} for n, q in popular],
            "by_status": {str(s): c for s, c in by_status},
        }


class DeliveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, delivery_id: int) -> Delivery | None:
        return self.session.get(Delivery, delivery_id)

    def by_order(self, order_id: int) -> Delivery | None:
        return self.session.scalars(select(Delivery).where(Delivery.order_id == order_id)).first()

    def find(self, status: DeliveryStatus | None) -> list[Delivery]:
        stmt = select(Delivery).order_by(Delivery.id.desc())
        if status is not None:
            stmt = stmt.where(Delivery.status == status)
        return list(self.session.scalars(stmt))

    def courier_load(self) -> dict[str, int]:
        active = [DeliveryStatus.ASSIGNED, DeliveryStatus.ON_THE_WAY]
        rows = self.session.execute(
            select(Delivery.courier, func.count(Delivery.id))
            .where(Delivery.status.in_(active))
            .group_by(Delivery.courier)
        ).all()
        return {courier: count for courier, count in rows if courier}


class OutboxRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, event_type: str, payload: dict) -> OutboxEvent:
        event = OutboxEvent(event_type=event_type, payload=payload)
        self.session.add(event)
        self.session.flush()
        return event

    def pending(self, limit: int = 50) -> list[OutboxEvent]:
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.id)
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def mark_published(self, event: OutboxEvent) -> None:
        event.published_at = datetime.now()
        event.attempts += 1

    def backlog(self) -> int:
        return self.session.scalar(
            select(func.count(OutboxEvent.id)).where(OutboxEvent.published_at.is_(None))
        )
