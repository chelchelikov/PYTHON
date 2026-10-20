from datetime import date

from models.entities import Room


class WeekendTariff:
    """Ночи с пятницы на субботу и с субботы на воскресенье дороже на 20 %."""

    name = "weekend"
    title = "Тариф выходного дня"
    markup = 0.2

    def night_price(self, room: Room, night: date) -> float:
        if night.weekday() in (4, 5):
            return room.base_price * (1 + self.markup)
        return room.base_price
