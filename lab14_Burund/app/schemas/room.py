from enum import Enum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator


class RoomType(str, Enum):
    standard = "standard"
    deluxe = "deluxe"
    suite = "suite"
    family = "family"


class SortField(str, Enum):
    number = "number"
    price = "price"
    floor = "floor"
    capacity = "capacity"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


def _clean_amenities(value: list[str]) -> list[str]:
    return sorted({item.strip().lower() for item in value if item.strip()})


Amenities = Annotated[list[str], AfterValidator(_clean_amenities)]


class RoomBase(BaseModel):
    number: str = Field(min_length=1, max_length=10, examples=["305"],
                        description="Номер комнаты")
    room_type: RoomType = Field(examples=["deluxe"], description="Тип номера")
    floor: int = Field(ge=0, le=100, examples=[3])
    capacity: int = Field(gt=0, le=10, examples=[2], description="Вместимость, человек")
    price: float = Field(gt=0, le=1_000_000, examples=[5500], description="Цена за ночь, ₽")
    is_available: bool = Field(default=True, description="Доступен для бронирования")
    amenities: Amenities = Field(default_factory=list, examples=[["wifi", "minibar"]])

    @field_validator("number")
    @classmethod
    def number_is_alnum(cls, value: str) -> str:
        value = value.strip()
        if not value.isalnum():
            raise ValueError("Номер комнаты должен состоять из букв и цифр")
        return value


class RoomCreate(RoomBase):
    """Данные для создания номера (POST) и полной замены (PUT)."""


class RoomPatch(BaseModel):
    """Частичное изменение: передаются только изменяемые поля."""

    number: str | None = Field(default=None, min_length=1, max_length=10)
    room_type: RoomType | None = None
    floor: int | None = Field(default=None, ge=0, le=100)
    capacity: int | None = Field(default=None, gt=0, le=10)
    price: float | None = Field(default=None, gt=0, le=1_000_000)
    is_available: bool | None = None
    amenities: Amenities | None = None


class RoomResponse(RoomBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class RoomListResponse(BaseModel):
    total: int = Field(description="Сколько номеров удовлетворяет фильтрам")
    limit: int
    offset: int
    items: list[RoomResponse]


class TypeStatistics(BaseModel):
    room_type: str
    count: int
    average_price: float


class RoomStatistics(BaseModel):
    total: int
    available: int
    occupancy_percent: float
    average_price: float
    min_price: float
    max_price: float
    total_capacity: int
    by_type: list[TypeStatistics]
