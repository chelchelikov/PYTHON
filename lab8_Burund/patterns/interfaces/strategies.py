from datetime import date
from typing import Protocol

from models.entities import Room


class PricingStrategy(Protocol):
    name: str

    def night_price(self, room: Room, night: date) -> float:
        """Стоимость одной ночи, начинающейся в дату night."""
        ...
