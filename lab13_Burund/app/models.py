"""Модель предметной области: номер отеля (документ MongoDB)."""

from dataclasses import asdict, dataclass, field
from typing import Any

ROOM_TYPES = ("standard", "deluxe", "suite", "family")
STATES = ("free", "booked", "occupied", "maintenance")
VIEWS = ("city", "sea", "park", "courtyard")


class ValidationError(ValueError):
    pass


@dataclass
class Features:
    """Вложенный документ: характеристики номера."""

    area_m2: float
    beds: int
    view: str
    smoking: bool = False
    balcony: bool = False


@dataclass
class Room:
    number: str
    room_type: str
    floor: int
    price: float
    state: str
    features: Features
    amenities: list[str] = field(default_factory=list)
    id: str | None = None

    def validate(self) -> "Room":
        if not self.number.strip():
            raise ValidationError("Номер комнаты обязателен")
        if self.room_type not in ROOM_TYPES:
            raise ValidationError(f"Тип номера: {', '.join(ROOM_TYPES)}")
        if self.state not in STATES:
            raise ValidationError(f"Состояние: {', '.join(STATES)}")
        if self.floor < 0:
            raise ValidationError("Этаж не может быть отрицательным")
        if self.price <= 0:
            raise ValidationError("Цена должна быть положительной")
        if self.features.area_m2 <= 0 or self.features.beds <= 0:
            raise ValidationError("Площадь и количество кроватей должны быть положительными")
        if self.features.view not in VIEWS:
            raise ValidationError(f"Вид из окна: {', '.join(VIEWS)}")
        if not all(isinstance(a, str) and a for a in self.amenities):
            raise ValidationError("Удобства — список непустых строк")
        return self

    def to_document(self) -> dict[str, Any]:
        document = asdict(self)
        document.pop("id")
        return document

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> "Room":
        data = dict(document)
        room_id = str(data.pop("_id")) if "_id" in data else data.pop("id", None)
        try:
            features = Features(**data.pop("features"))
            return cls(**data, features=features, id=room_id)
        except (KeyError, TypeError) as error:
            raise ValidationError(f"Некорректный документ: {error}") from None

    def to_dict(self) -> dict[str, Any]:
        return {**self.to_document(), "id": self.id}
