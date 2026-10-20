"""ORM-модели: User (клиент), Dish, Order, OrderItem, Delivery, OutboxEvent."""

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(enum.StrEnum):
    USER = "user"
    ADMIN = "admin"


class DishCategory(enum.StrEnum):
    SALAD = "salad"
    SOUP = "soup"
    MAIN = "main"
    DESSERT = "dessert"
    DRINK = "drink"


class OrderStatus(enum.StrEnum):
    CREATED = "created"
    COOKING = "cooking"
    READY = "ready"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class DeliveryStatus(enum.StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    ON_THE_WAY = "on_the_way"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


def _enum(cls):
    return Enum(cls, values_callable=lambda e: [m.value for m in e], native_enum=False, length=20)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[Role] = mapped_column(_enum(Role), nullable=False, default=Role.USER)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    orders: Mapped[list["Order"]] = relationship(back_populates="user")


class Dish(Base):
    __tablename__ = "dishes"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_dish_price"),
        CheckConstraint("portions_available >= 0", name="ck_dish_portions"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[DishCategory] = mapped_column(_enum(DishCategory), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    portions_available: Mapped[int] = mapped_column(nullable=False, default=50)
    is_available: Mapped[bool] = mapped_column(nullable=False, default=True)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("total >= 0", name="ck_order_total"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        _enum(OrderStatus), nullable=False, default=OrderStatus.CREATED, index=True
    )
    address: Mapped[str] = mapped_column(String(200), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    items_total: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    delivery_fee: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    total: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )
    delivery: Mapped["Delivery | None"] = relationship(
        back_populates="order", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "dish_id", name="uq_order_dish"),
        CheckConstraint("quantity > 0", name="ck_item_quantity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    dish_id: Mapped[int] = mapped_column(
        ForeignKey("dishes.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    dish: Mapped[Dish] = relationship(lazy="selectin")


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[DeliveryStatus] = mapped_column(
        _enum(DeliveryStatus), nullable=False, default=DeliveryStatus.PENDING
    )
    courier: Mapped[str | None] = mapped_column(String(50))
    eta_minutes: Mapped[int | None] = mapped_column()
    address: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    order: Mapped[Order] = relationship(back_populates="delivery")


class OutboxEvent(Base):
    """Transactional Outbox: событие сохраняется в той же транзакции, что и заказ."""

    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)
