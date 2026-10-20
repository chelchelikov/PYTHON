class RestaurantError(Exception):
    """Базовое исключение приложения."""


class NotFoundError(RestaurantError):
    pass


class DuplicateError(RestaurantError):
    pass


class ValidationError(RestaurantError):
    pass


class OrderError(RestaurantError):
    """Ошибка бизнес-операции с заказом (транзакция отменена)."""
