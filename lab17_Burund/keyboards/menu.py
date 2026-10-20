from aiogram.filters.callback_data import CallbackData
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
                           ReplyKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.repositories import Booking, Room, RoomType

BTN_SEARCH = "🔎 Свободные номера"
BTN_BOOK = "🛎 Забронировать"
BTN_MY = "📋 Мои бронирования"
BTN_TYPES = "🏨 Типы номеров"
BTN_HELP = "❓ Помощь"
BTN_CANCEL = "✖ Отмена"


class TypeCallback(CallbackData, prefix="type"):
    action: str  # "show" — список номеров типа, "pick" — выбор в FSM
    type_id: int  # 0 — любой тип


class RoomCallback(CallbackData, prefix="room"):
    action: str  # "pick" — выбор номера в FSM, "info" — карточка
    room_id: int


class BookingCallback(CallbackData, prefix="bk"):
    action: str  # show / cancel / dates / delete
    booking_id: int


class ConfirmCallback(CallbackData, prefix="confirm"):
    answer: str  # yes / no


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=BTN_SEARCH), KeyboardButton(text=BTN_BOOK)],
        [KeyboardButton(text=BTN_MY), KeyboardButton(text=BTN_TYPES)],
        [KeyboardButton(text=BTN_HELP)],
    ], resize_keyboard=True, input_field_placeholder="Выберите действие")


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
                               resize_keyboard=True)


def room_types_keyboard(types: list[RoomType], action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for room_type in types:
        builder.button(text=room_type.name,
                       callback_data=TypeCallback(action=action, type_id=room_type.id))
    if action == "pick":
        builder.button(text="Любой тип", callback_data=TypeCallback(action=action, type_id=0))
    builder.adjust(2)
    return builder.as_markup()


def rooms_keyboard(rooms: list[Room], action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for room in rooms[:20]:
        builder.button(text=f"№{room.number} · {room.type_name} · {room.price:.0f} ₽",
                       callback_data=RoomCallback(action=action, room_id=room.id))
    builder.adjust(1)
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    yes = ConfirmCallback(answer="yes").pack()
    no = ConfirmCallback(answer="no").pack()
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=yes),
        InlineKeyboardButton(text="❌ Отменить", callback_data=no),
    ]])


def bookings_keyboard(bookings: list[Booking]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for booking in bookings[:20]:
        mark = "🟢" if booking.status == "active" else "⚪"
        builder.button(text=f"{mark} #{booking.id} · №{booking.room_number} · "
                            f"{booking.check_in:%d.%m}–{booking.check_out:%d.%m}",
                       callback_data=BookingCallback(action="show", booking_id=booking.id))
    builder.adjust(1)
    return builder.as_markup()


def booking_actions(booking: Booking) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if booking.status == "active":
        builder.button(text="📅 Изменить даты",
                       callback_data=BookingCallback(action="dates", booking_id=booking.id))
        builder.button(text="🚫 Отменить бронь",
                       callback_data=BookingCallback(action="cancel", booking_id=booking.id))
    else:
        builder.button(text="🗑 Удалить из истории",
                       callback_data=BookingCallback(action="delete", booking_id=booking.id))
    builder.adjust(1)
    return builder.as_markup()
