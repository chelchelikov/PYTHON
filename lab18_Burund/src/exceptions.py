class HotelError(Exception):
    """Базовая ошибка предметной области."""


class NotFoundError(HotelError):
    pass


class ValidationError(HotelError):
    pass


class BookingConflictError(HotelError):
    """Период пересекается с существующим бронированием."""


class OperationNotAllowedError(HotelError):
    pass
