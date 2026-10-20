from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from handlers.texts import HELP
from keyboards.menu import BTN_CANCEL, BTN_HELP, main_menu
from services.hotel import HotelService

ROUTER_NAME = "common"


async def cmd_start(message: Message, state: FSMContext, service: HotelService) -> None:
    await state.clear()
    await service.register(message.from_user.id, message.from_user.full_name)
    await message.answer(f"Здравствуйте, {message.from_user.first_name}! "
                         f"Я помогу подобрать и забронировать номер.\n\n{HELP}",
                         reply_markup=main_menu())


async def cmd_help(message: Message) -> None:
    await message.answer(HELP, reply_markup=main_menu())


async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer("Нечего отменять.", reply_markup=main_menu())
        return
    await state.clear()
    await message.answer("Операция отменена.", reply_markup=main_menu())


def create_router() -> Router:
    router = Router(name=ROUTER_NAME)
    router.message.register(cmd_start, CommandStart())
    router.message.register(cmd_help, Command("help"))
    router.message.register(cmd_help, F.text == BTN_HELP)
    router.message.register(cmd_cancel, Command("cancel"), StateFilter("*"))
    router.message.register(cmd_cancel, F.text == BTN_CANCEL, StateFilter("*"))
    return router
