"""Factory + Strategy: фабрика создаёт тариф по его названию."""

from interfaces.strategies import PricingStrategy
from models.entities import HotelError
from strategies.regular import RegularTariff
from strategies.seasonal import SeasonalTariff
from strategies.weekend import WeekendTariff


class StrategyFactory:
    _strategies: dict[str, type] = {
        "regular": RegularTariff,
        "seasonal": SeasonalTariff,
        "weekend": WeekendTariff,
    }

    @classmethod
    def names(cls) -> list[str]:
        return list(cls._strategies)

    @classmethod
    def create(cls, name: str) -> PricingStrategy:
        try:
            return cls._strategies[name]()
        except KeyError:
            raise HotelError(f"Неизвестный тариф: {name}") from None
