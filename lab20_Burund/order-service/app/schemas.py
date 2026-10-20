from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class OrderStatus(StrEnum):
    created = "created"
    cooking = "cooking"
    ready = "ready"
    delivered = "delivered"
    cancelled = "cancelled"


class ItemIn(BaseModel):
    dish_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=20)


class OrderIn(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=5, max_length=20)
    address: str = Field(min_length=5, max_length=200)
    items: list[ItemIn] = Field(min_length=1, max_length=30)


class OrderUpdate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=5, max_length=20)
    address: str = Field(min_length=5, max_length=200)
    status: OrderStatus


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dish_id: int
    name: str
    price: float
    quantity: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_name: str
    phone: str
    address: str
    status: OrderStatus
    total: float
    created_at: datetime | None
    items: list[ItemOut]
