from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.texts import booking_card
from keyboards.menu import (BTN_MY, BookingCallback, booking_actions, bookings_keyboard,
                            cancel_menu, main_menu)
from services.hotel import BookingError, HotelService
from services.validation import InputError, parse_check_out, parse_date
from states.booking import ChangeDatesForm

ROUTER_NAME = "my_bookings"


async def my_bookings(message: Message, service: HotelService) -> None:
    bookings = await service.history(message.from_user.id, message.from_user.full_name)
    if not bookings:
        await message.answer("У вас пока нет бронирований. Забронировать — /book")
        return
    active = sum(1 for b in bookings if b.status == "active")
    await message.answer(f"Ваши бронирования (активных: {active}, всего: {len(bookings)}):",
                         reply_markup=bookings_keyboard(bookings))


async def show_booking(callback: CallbackQuery, callback_data: BookingCallback,
                       service: HotelService) -> None:
    try:
        booking = await service.get_booking(callback.from_user.id, callback_data.booking_id)
    except BookingError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.message.answer(booking_card(booking), reply_markup=booking_actions(booking))
    await callback.answer()


async def cancel_booking(callback: CallbackQuery, callback_data: BookingCallback,
                         service: HotelService) -> None:
    try:
        booking = await service.cancel(callback.from_user.id, callback_data.booking_id)
    except BookingError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.message.edit_text("Бронирование отменено.\n\n" + booking_card(booking),
                                     reply_markup=booking_actions(booking))
    await callback.answer("Отменено")


async def delete_booking(callback: CallbackQuery, callback_data: BookingCallback,
                         service: HotelService) -> None:
    try:
        await service.delete_cancelled(callback.from_user.id, callback_data.booking_id)
    except BookingError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.message.edit_text(
        f"Бронирование #{callback_data.booking_id} удалено из истории.")
    await callback.answer()


async def change_dates_start(callback: CallbackQuery, callback_data: BookingCallback,
                             state: FSMContext, service: HotelService) -> None:
    try:
        await service.get_booking(callback.from_user.id, callback_data.booking_id)
    except BookingError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await state.set_state(ChangeDatesForm.check_in)
    await state.update_data(booking_id=callback_data.booking_id)
    await callback.message.answer("Новая дата заезда (ДД.ММ.ГГГГ):", reply_markup=cancel_menu())
    await callback.answer()


async def change_check_in(message: Message, state: FSMContext) -> None:
    try:
        check_in = parse_date(message.text)
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return
    await state.update_data(check_in=check_in.isoformat())
    await state.set_state(ChangeDatesForm.check_out)
    await message.answer("Новая дата выезда (ДД.ММ.ГГГГ):")


async def change_check_out(message: Message, state: FSMContext, service: HotelService) -> None:
    data = await state.get_data()
    check_in = date.fromisoformat(data["check_in"])
    try:
        check_out = parse_check_out(message.text, check_in)
        booking = await service.change_dates(message.from_user.id, data["booking_id"],
                                             check_in, check_out)
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return
    except BookingError as error:
        await state.clear()
        await message.answer(f"⚠️ {error}", reply_markup=main_menu())
        return
    await state.clear()
    await message.answer("Даты изменены.\n\n" + booking_card(booking), reply_markup=main_menu())


def create_router() -> Router:
    router = Router(name=ROUTER_NAME)
    router.message.register(my_bookings, Command("mybookings"))
    router.message.register(my_bookings, F.text == BTN_MY)
    router.callback_query.register(show_booking, BookingCallback.filter(F.action == "show"))
    router.callback_query.register(cancel_booking, BookingCallback.filter(F.action == "cancel"))
    router.callback_query.register(delete_booking, BookingCallback.filter(F.action == "delete"))
    router.callback_query.register(change_dates_start, BookingCallback.filter(F.action == "dates"))
    router.message.register(change_check_in, ChangeDatesForm.check_in, F.text)
    router.message.register(change_check_out, ChangeDatesForm.check_out, F.text)
    return router
