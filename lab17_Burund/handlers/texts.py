from database.repositories import Booking, Room
from services.validation import format_date

HELP = (
    "<b>Бот гостиницы «Северная звезда»</b>\n\n"
    "/search — найти свободные номера на даты\n"
    "/book — забронировать номер (пошагово)\n"
    "/mybookings — история бронирований, изменение дат и отмена\n"
    "/types — типы номеров\n"
    "/cancel — прервать текущую операцию\n"
    "/help — эта справка\n\n"
    "Даты вводятся в формате ДД.ММ.ГГГГ."
)

STATUS = {"active": "🟢 активно", "cancelled": "⚪ отменено"}


def room_card(room: Room) -> str:
    state = "" if room.is_active else "\n⚠️ Временно недоступен"
    return (f"<b>Номер {room.number}</b> — {room.type_name}\n"
            f"Этаж: {room.floor}, мест: {room.capacity}\n"
            f"Цена: {room.price:.0f} ₽ за ночь{state}")


def booking_card(booking: Booking) -> str:
    return (f"<b>Бронирование #{booking.id}</b> — {STATUS.get(booking.status, booking.status)}\n"
            f"Номер {booking.room_number} ({booking.room_type})\n"
            f"{format_date(booking.check_in)} — {format_date(booking.check_out)} "
            f"({booking.nights} ноч.), гостей: {booking.guests}\n"
            f"Стоимость: {booking.total:.0f} ₽")
