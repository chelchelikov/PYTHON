from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

from keyboards.menu import main_menu

ROUTER_NAME = "fallback"


async def unknown_command(message: Message) -> None:
    await message.answer("Неизвестная команда. Список команд — /help")


async def unknown_text(message: Message) -> None:
    await message.answer("Не понял сообщение. Выберите действие в меню или отправьте /help.",
                         reply_markup=main_menu())


async def unsupported_content(message: Message) -> None:
    await message.answer("Я понимаю только текст и кнопки. Если вы заполняли форму — "
                         "введите значение текстом или отправьте /cancel.")


async def stale_callback(callback: CallbackQuery) -> None:
    await callback.answer("Эта кнопка устарела. Начните заново через меню.", show_alert=True)


def create_router() -> Router:
    router = Router(name=ROUTER_NAME)
    router.message.register(unknown_command, StateFilter(None), F.text.startswith("/"))
    router.message.register(unknown_text, F.text)
    router.message.register(unsupported_content)
    router.callback_query.register(stale_callback)
    return router
