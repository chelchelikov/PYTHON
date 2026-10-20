from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Category(StrEnum):
    salad = "salad"
    soup = "soup"
    main = "main"
    dessert = "dessert"
    drink = "drink"


class DishIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: Category
    price: float = Field(gt=0, le=100_000)
    is_available: bool = True


class DishPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: Category | None = None
    price: float | None = Field(default=None, gt=0, le=100_000)
    is_available: bool | None = None


class DishOut(DishIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
