"""Лабораторная работа №17. Вариант 5. Отель — Telegram-бот на aiogram 3.

Запуск: BOT_TOKEN=... python bot.py
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent

from config import Config, load_config
from database.db import Database
from handlers import setup_routers
from middlewares.logging import ActivityMiddleware
from middlewares.service import ServiceMiddleware
from services.hotel import HotelService

log = logging.getLogger("hotel_bot")

COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="search", description="Свободные номера"),
    BotCommand(command="book", description="Забронировать"),
    BotCommand(command="mybookings", description="Мои бронирования"),
    BotCommand(command="types", description="Типы номеров"),
    BotCommand(command="cancel", description="Отменить операцию"),
    BotCommand(command="help", description="Справка"),
]


def create_dispatcher(service: HotelService, config: Config) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage(), config=config)
    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(ServiceMiddleware(service))
        observer.middleware(ActivityMiddleware())
    dispatcher.include_router(setup_routers())

    @dispatcher.errors()
    async def on_error(event: ErrorEvent) -> bool:
        log.exception("Ошибка при обработке update %s", event.update.update_id,
                      exc_info=event.exception)
        message = event.update.message or (event.update.callback_query and
                                           event.update.callback_query.message)
        if message is not None:
            await message.answer("Произошла ошибка. Попробуйте ещё раз или отправьте /start.")
        return True

    return dispatcher


async def main() -> None:
    config = load_config()
    logging.basicConfig(level=config.log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.bot_token:
        raise SystemExit("Не задан BOT_TOKEN (см. .env.example)")
    database = Database(config.db_path)
    await database.connect()
    if await database.seed():
        log.info("База заполнена демонстрационными данными")
    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = create_dispatcher(HotelService(database.connection), config)
    await bot.set_my_commands(COMMANDS)
    log.info("Бот запущен")
    try:
        await dispatcher.start_polling(bot)
    finally:
        await database.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
