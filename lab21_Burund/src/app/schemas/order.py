from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import DeliveryStatus, OrderStatus


class OrderItemIn(BaseModel):
    dish_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=20)


class OrderIn(BaseModel):
    address: str = Field(min_length=5, max_length=200)
    comment: str = Field(default="", max_length=500)
    items: list[OrderItemIn] = Field(min_length=1, max_length=30)

    @field_validator("items")
    @classmethod
    def unique_dishes(cls, items: list[OrderItemIn]) -> list[OrderItemIn]:
        ids = [item.dish_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Каждое блюдо указывается один раз — используйте quantity")
        return items


class StatusIn(BaseModel):
    status: OrderStatus


class DeliveryPatch(BaseModel):
    status: DeliveryStatus | None = None
    courier: str | None = Field(default=None, min_length=1, max_length=50)
    eta_minutes: int | None = Field(default=None, ge=0, le=600)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dish_id: int
    quantity: int
    price: float
    dish_name: str = ""


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    status: DeliveryStatus
    courier: str | None
    eta_minutes: int | None
    address: str


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    status: OrderStatus
    address: str
    comment: str
    items_total: float
    delivery_fee: float
    total: float
    created_at: datetime | None
    items: list[OrderItemOut]
    delivery: DeliveryOut | None

    @classmethod
    def from_order(cls, order) -> "OrderOut":
        result = cls.model_validate(order)
        for item_out, item in zip(result.items, order.items, strict=True):
            item_out.dish_name = item.dish.name
        return result
