"""Пользовательские исключения гостиницы."""


class HotelError(Exception):
    """Базовое исключение предметной области."""


class EntityNotFoundError(HotelError):
    pass


class InvalidStatusError(HotelError):
    """Недопустимое изменение состояния номера."""


class BookingError(HotelError):
    pass
