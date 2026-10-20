"""ORM-модели ресторана (SQLAlchemy 2.x)."""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DishCategory(enum.Enum):
    SALAD = "салат"
    SOUP = "суп"
    MAIN = "горячее"
    DESSERT = "десерт"
    DRINK = "напиток"


class OrderStatus(enum.Enum):
    NEW = "новый"
    COOKING = "готовится"
    SERVED = "подан"
    PAID = "оплачен"
    CANCELLED = "отменён"


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")

    def __repr__(self) -> str:
        return f"Customer(id={self.id}, name={self.name!r}, phone={self.phone!r})"


class Dish(Base):
    __tablename__ = "dishes"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_dish_price_positive"),
        CheckConstraint("portions_left >= 0", name="ck_dish_portions_non_negative"),
        CheckConstraint("weight_g > 0", name="ck_dish_weight_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    category: Mapped[DishCategory] = mapped_column(Enum(DishCategory), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    weight_g: Mapped[int] = mapped_column(nullable=False)
    portions_left: Mapped[int] = mapped_column(nullable=False, default=0)
    is_available: Mapped[bool] = mapped_column(nullable=False, default=True)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="dish")

    def __repr__(self) -> str:
        return f"Dish(id={self.id}, name={self.name!r}, price={self.price})"


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("total >= 0", name="ck_order_total_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"),
                                             nullable=False, index=True)
    table_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False,
                                                default=OrderStatus.NEW)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order",
                                                    cascade="all, delete-orphan")

    def calculate_total(self) -> Decimal:
        return sum((item.price * item.quantity for item in self.items), Decimal("0"))

    def __repr__(self) -> str:
        return f"Order(id={self.id}, status={self.status.value}, total={self.total})"


class OrderItem(Base):
    """Позиция заказа — связь many-to-many между заказами и блюдами."""

    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "dish_id", name="uq_order_dish"),
        CheckConstraint("quantity > 0", name="ck_item_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"),
                                          nullable=False)
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id", ondelete="RESTRICT"),
                                         nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # цена на момент заказа

    order: Mapped[Order] = relationship(back_populates="items")
    dish: Mapped[Dish] = relationship(back_populates="items")
