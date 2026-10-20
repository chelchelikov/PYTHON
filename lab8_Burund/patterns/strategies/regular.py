from datetime import date

from models.entities import Room


class RegularTariff:
    name = "regular"
    title = "Обычный тариф"

    def night_price(self, room: Room, night: date) -> float:
        return room.base_price
