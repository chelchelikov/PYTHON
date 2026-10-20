"""Проверка пользовательского ввода. Каждая ошибка — отдельное понятное сообщение."""

from datetime import date, datetime

MAX_NIGHTS = 30
MAX_GUESTS = 6
DATE_FORMAT = "%d.%m.%Y"


class InputError(ValueError):
    """Некорректный ввод пользователя."""


def parse_date(text: str, today: date | None = None) -> date:
    today = today or date.today()
    try:
        value = datetime.strptime(text.strip(), DATE_FORMAT).date()
    except (ValueError, AttributeError):
        raise InputError("Введите дату в формате ДД.ММ.ГГГГ, например 05.12.2026") from None
    if value < today:
        raise InputError("Дата не может быть в прошлом")
    if (value - today).days > 365:
        raise InputError("Бронирование возможно не более чем на год вперёд")
    return value


def parse_check_out(text: str, check_in: date, today: date | None = None) -> date:
    value = parse_date(text, today)
    if value <= check_in:
        raise InputError("Дата выезда должна быть позже даты заезда")
    if (value - check_in).days > MAX_NIGHTS:
        raise InputError(f"Максимальный срок проживания — {MAX_NIGHTS} ночей")
    return value


def parse_guests(text: str) -> int:
    if not text or not text.strip().isdigit():
        raise InputError("Количество гостей нужно ввести числом, например 2")
    value = int(text)
    if not 1 <= value <= MAX_GUESTS:
        raise InputError(f"Количество гостей — от 1 до {MAX_GUESTS}")
    return value


def format_date(value: date) -> str:
    return value.strftime(DATE_FORMAT)
