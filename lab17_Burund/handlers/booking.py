"""Пошаговое бронирование (FSM): заезд → выезд → гости → тип → номер → подтверждение."""

from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.texts import booking_card, room_card
from keyboards.menu import (BTN_BOOK, ConfirmCallback, RoomCallback, TypeCallback, cancel_menu,
                            confirm_keyboard, main_menu, room_types_keyboard, rooms_keyboard)
from services.hotel import BookingError, HotelService
from services.validation import InputError, format_date, parse_check_out, parse_date, parse_guests
from states.booking import BookingForm

ROUTER_NAME = "booking"


async def period_from(state: FSMContext) -> tuple[date, date, int, dict]:
    data = await state.get_data()
    return (date.fromisoformat(data["check_in"]), date.fromisoformat(data["check_out"]),
            data["guests"], data)


async def booking_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BookingForm.check_in)
    await message.answer("Шаг 1/5. Введите дату заезда (ДД.ММ.ГГГГ):",
                         reply_markup=cancel_menu())


async def booking_check_in(message: Message, state: FSMContext) -> None:
    try:
        check_in = parse_date(message.text)
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return
    await state.update_data(check_in=check_in.isoformat())
    await state.set_state(BookingForm.check_out)
    await message.answer("Шаг 2/5. Дата выезда (ДД.ММ.ГГГГ):")


async def booking_check_out(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        check_out = parse_check_out(message.text, date.fromisoformat(data["check_in"]))
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return
    await state.update_data(check_out=check_out.isoformat())
    await state.set_state(BookingForm.guests)
    await message.answer("Шаг 3/5. Количество гостей:")


async def booking_guests(message: Message, state: FSMContext, service: HotelService) -> None:
    try:
        guests = parse_guests(message.text)
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return
    await state.update_data(guests=guests)
    await state.set_state(BookingForm.room_type)
    await message.answer("Шаг 4/5. Выберите тип номера:",
                         reply_markup=room_types_keyboard(await service.room_types(), "pick"))


async def booking_room_type(callback: CallbackQuery, callback_data: TypeCallback,
                            state: FSMContext, service: HotelService) -> None:
    check_in, check_out, guests, _ = await period_from(state)
    rooms = await service.search_free(check_in, check_out, guests, callback_data.type_id or None)
    if not rooms:
        await callback.answer("Нет свободных номеров этого типа на выбранные даты — "
                              "выберите другой тип", show_alert=True)
        return
    await state.set_state(BookingForm.room)
    await callback.message.edit_text(
        f"Шаг 5/5. Свободные номера на {format_date(check_in)} — {format_date(check_out)}:",
        reply_markup=rooms_keyboard(rooms, "pick"))
    await callback.answer()


async def booking_room(callback: CallbackQuery, callback_data: RoomCallback, state: FSMContext,
                       service: HotelService) -> None:
    check_in, check_out, guests, _ = await period_from(state)
    room = await service.get_room(callback_data.room_id)
    total = room.price * (check_out - check_in).days
    await state.update_data(room_id=room.id)
    await state.set_state(BookingForm.confirm)
    await callback.message.edit_text(
        f"Проверьте данные:\n\n{room_card(room)}\n\n"
        f"Даты: {format_date(check_in)} — {format_date(check_out)} "
        f"({(check_out - check_in).days} ноч.)\nГостей: {guests}\n<b>Итого: {total:.0f} ₽</b>",
        reply_markup=confirm_keyboard())
    await callback.answer()


async def booking_confirm(callback: CallbackQuery, callback_data: ConfirmCallback,
                          state: FSMContext, service: HotelService) -> None:
    if callback_data.answer != "yes":
        await state.clear()
        await callback.message.edit_text("Бронирование отменено.")
        await callback.message.answer("Главное меню:", reply_markup=main_menu())
        await callback.answer()
        return
    check_in, check_out, guests, data = await period_from(state)
    try:
        booking = await service.book(callback.from_user.id, callback.from_user.full_name,
                                     data["room_id"], check_in, check_out, guests)
    except (BookingError, InputError) as error:
        await callback.answer(str(error), show_alert=True)
        return
    finally:
        await state.clear()
    await callback.message.edit_text("✅ Номер забронирован!\n\n" + booking_card(booking))
    await callback.message.answer("Главное меню:", reply_markup=main_menu())
    await callback.answer("Готово")


async def booking_expect_button(message: Message) -> None:
    await message.answer("Пожалуйста, воспользуйтесь кнопками под сообщением "
                         "или отправьте /cancel.")


def create_router() -> Router:
    router = Router(name=ROUTER_NAME)
    router.message.register(booking_start, Command("book"))
    router.message.register(booking_start, F.text == BTN_BOOK)
    router.message.register(booking_check_in, BookingForm.check_in, F.text)
    router.message.register(booking_check_out, BookingForm.check_out, F.text)
    router.message.register(booking_guests, BookingForm.guests, F.text)
    router.callback_query.register(booking_room_type, BookingForm.room_type,
                                   TypeCallback.filter(F.action == "pick"))
    router.callback_query.register(booking_room, BookingForm.room,
                                   RoomCallback.filter(F.action == "pick"))
    router.callback_query.register(booking_confirm, BookingForm.confirm, ConfirmCallback.filter())
    router.message.register(booking_expect_button, BookingForm.room_type)
    router.message.register(booking_expect_button, BookingForm.room)
    router.message.register(booking_expect_button, BookingForm.confirm)
    return router
