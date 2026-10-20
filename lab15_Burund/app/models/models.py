import enum
from datetime import datetime

from sqlalchemy import (CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderStatus(enum.Enum):
    NEW = "новый"
    COOKING = "готовится"
    SERVED = "подан"
    PAID = "оплачен"
    CANCELLED = "отменён"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    dishes: Mapped[list["Dish"]] = relationship(back_populates="category",
                                                order_by="Dish.name")

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description,
                "dishes_count": len(self.dishes)}


class Dish(Base):
    __tablename__ = "dishes"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_dish_price"),
        CheckConstraint("weight_g > 0", name="ck_dish_weight"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    weight_g: Mapped[int] = mapped_column(nullable=False)
    is_available: Mapped[bool] = mapped_column(nullable=False, default=True)
    is_vegetarian: Mapped[bool] = mapped_column(nullable=False, default=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"),
                                             nullable=False, index=True)

    category: Mapped[Category] = relationship(back_populates="dishes")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="dish")

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description,
                "price": self.price, "weight_g": self.weight_g,
                "is_available": self.is_available, "is_vegetarian": self.is_vegetarian,
                "category": {"id": self.category.id, "name": self.category.name}}


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("table_number > 0", name="ck_order_table"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    table_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False,
                                                default=OrderStatus.NEW)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order",
                                                    cascade="all, delete-orphan")

    @property
    def total(self) -> float:
        return round(sum(item.price * item.quantity for item in self.items), 2)

    def to_dict(self) -> dict:
        return {"id": self.id, "customer_name": self.customer_name,
                "table_number": self.table_number, "status": self.status.name.lower(),
                "status_title": self.status.value, "comment": self.comment,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "total": self.total,
                "items": [{"dish_id": i.dish_id, "dish": i.dish.name, "quantity": i.quantity,
                           "price": i.price} for i in self.items]}


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "dish_id", name="uq_order_item"),
        CheckConstraint("quantity > 0", name="ck_item_quantity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"),
                                          nullable=False)
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id", ondelete="RESTRICT"),
                                         nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    dish: Mapped[Dish] = relationship(back_populates="items")
