from datetime import date

from models.entities import Room


class SeasonalTariff:
    """Высокий сезон: летние месяцы и новогодние праздники (+30 %)."""

    name = "seasonal"
    title = "Сезонный тариф"
    markup = 0.3

    @staticmethod
    def is_high_season(night: date) -> bool:
        return (night.month in (6, 7, 8)
                or (night.month == 12 and night.day >= 20)
                or (night.month == 1 and night.day <= 10))

    def night_price(self, room: Room, night: date) -> float:
        if self.is_high_season(night):
            return room.base_price * (1 + self.markup)
        return room.base_price
