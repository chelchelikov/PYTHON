from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DeliveryStatus(str, Enum):
    assigned = "assigned"
    on_the_way = "on_the_way"
    delivered = "delivered"
    cancelled = "cancelled"


class DeliveryIn(BaseModel):
    order_id: int = Field(gt=0)
    customer_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=5, max_length=20)
    address: str = Field(min_length=5, max_length=200)
    order_total: float = Field(ge=0)


class DeliveryUpdate(BaseModel):
    address: str = Field(min_length=5, max_length=200)
    courier: str = Field(min_length=1, max_length=50)
    status: DeliveryStatus
    eta_minutes: int = Field(ge=0, le=600)


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    customer_name: str
    phone: str
    address: str
    order_total: float
    courier: str | None
    status: DeliveryStatus
    eta_minutes: int
    created_at: datetime | None
