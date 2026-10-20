from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.texts import room_card
from keyboards.menu import (BTN_SEARCH, BTN_TYPES, RoomCallback, TypeCallback, cancel_menu,
                            main_menu, room_types_keyboard, rooms_keyboard)
from services.hotel import BookingError, HotelService
from services.validation import InputError, format_date, parse_check_out, parse_date, parse_guests
from states.booking import SearchForm

ROUTER_NAME = "rooms"


async def show_types(message: Message, service: HotelService) -> None:
    types = await service.room_types()
    text = "\n".join(f"<b>{t.name}</b> — {t.description}" for t in types)
    await message.answer(f"Типы номеров:\n\n{text}\n\nВыберите тип, чтобы увидеть номера:",
                         reply_markup=room_types_keyboard(types, "show"))


async def show_rooms_of_type(callback: CallbackQuery, callback_data: TypeCallback,
                             service: HotelService) -> None:
    rooms = await service.rooms_of_type(callback_data.type_id)
    if not rooms:
        await callback.answer("Номеров этого типа нет", show_alert=True)
        return
    await callback.message.answer(f"Номера типа «{rooms[0].type_name}»:",
                                  reply_markup=rooms_keyboard(rooms, "info"))
    await callback.answer()


async def room_info(callback: CallbackQuery, callback_data: RoomCallback,
                    service: HotelService) -> None:
    try:
        room = await service.get_room(callback_data.room_id)
    except BookingError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.message.answer(room_card(room) + "\n\nЧтобы забронировать — /book")
    await callback.answer()


# --- поиск свободных номеров ---
async def search_start(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchForm.check_in)
    await message.answer("Дата заезда (ДД.ММ.ГГГГ):", reply_markup=cancel_menu())


async def search_check_in(message: Message, state: FSMContext) -> None:
    try:
        check_in = parse_date(message.text)
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return
    await state.update_data(check_in=check_in.isoformat())
    await state.set_state(SearchForm.check_out)
    await message.answer("Дата выезда (ДД.ММ.ГГГГ):")


async def search_check_out(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        check_out = parse_check_out(message.text, date.fromisoformat(data["check_in"]))
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return
    await state.update_data(check_out=check_out.isoformat())
    await state.set_state(SearchForm.guests)
    await message.answer("Сколько гостей?")


async def search_guests(message: Message, state: FSMContext, service: HotelService) -> None:
    try:
        guests = parse_guests(message.text)
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return
    data = await state.get_data()
    await state.clear()
    check_in = date.fromisoformat(data["check_in"])
    check_out = date.fromisoformat(data["check_out"])
    rooms = await service.search_free(check_in, check_out, guests)
    period = f"{format_date(check_in)} — {format_date(check_out)}"
    if not rooms:
        await message.answer(f"На {period} для {guests} гостей свободных номеров нет 😔",
                             reply_markup=main_menu())
        return
    await message.answer(f"Свободно на {period} для {guests} гост.: {len(rooms)} номеров. "
                         f"Нажмите на номер, чтобы посмотреть подробности, "
                         f"или /book для бронирования.", reply_markup=main_menu())
    await message.answer("Номера (от дешёвых к дорогим):",
                         reply_markup=rooms_keyboard(rooms, "info"))


def create_router() -> Router:
    router = Router(name=ROUTER_NAME)
    router.message.register(show_types, Command("types"))
    router.message.register(show_types, F.text == BTN_TYPES)
    router.callback_query.register(show_rooms_of_type, TypeCallback.filter(F.action == "show"))
    router.callback_query.register(room_info, RoomCallback.filter(F.action == "info"))
    router.message.register(search_start, Command("search"))
    router.message.register(search_start, F.text == BTN_SEARCH)
    router.message.register(search_check_in, SearchForm.check_in, F.text)
    router.message.register(search_check_out, SearchForm.check_out, F.text)
    router.message.register(search_guests, SearchForm.guests, F.text)
    return router
