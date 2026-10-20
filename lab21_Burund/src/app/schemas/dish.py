from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models import DishCategory


class DishSort(StrEnum):
    name = "name"
    price = "price"
    price_desc = "-price"


class DishIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    category: DishCategory
    price: float = Field(gt=0, le=100_000)
    portions_available: int = Field(default=50, ge=0, le=10_000)
    is_available: bool = True


class DishPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    category: DishCategory | None = None
    price: float | None = Field(default=None, gt=0, le=100_000)
    portions_available: int | None = Field(default=None, ge=0, le=10_000)
    is_available: bool | None = None


class DishOut(DishIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class DishPage(BaseModel):
    total: int
    items: list[DishOut]
