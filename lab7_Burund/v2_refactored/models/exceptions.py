class HotelError(Exception):
    """Базовое исключение предметной области."""


class EntityNotFoundError(HotelError):
    pass


class RoomUnavailableError(HotelError):
    pass


class BookingError(HotelError):
    pass
