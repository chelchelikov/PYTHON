"""Тестовая инфраструктура: БД в памяти и «фальшивый» Telegram без сети."""

import itertools
from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from bot import create_dispatcher
from config import Config
from database.db import Database
from services.hotel import HotelService

ADMIN_ID = 1000
USER_ID = 2000


async def make_service() -> tuple[Database, HotelService]:
    database = Database(":memory:")
    await database.connect()
    await database.seed()
    return database, HotelService(database.connection)


class FakeSession(BaseSession):
    """Вместо HTTP-запросов к Telegram запоминает вызванные методы API."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod] = []
        self._ids = itertools.count(1)

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None):
        self.requests.append(method)
        if isinstance(method, (SendMessage, EditMessageText)):
            return Message(message_id=next(self._ids), date=datetime.now(),
                           chat=Chat(id=method.chat_id or USER_ID, type="private"),
                           text=method.text)
        if isinstance(method, AnswerCallbackQuery):
            return True
        return True

    async def close(self) -> None:
        pass

    async def stream_content(self, *args: Any, **kwargs: Any):
        yield b""


class TelegramEmulator:
    """Отправляет боту сообщения и нажатия кнопок через настоящий Dispatcher."""

    def __init__(self, service: HotelService, admin_ids=frozenset({ADMIN_ID})) -> None:
        self.session = FakeSession()
        self.bot = Bot("42:TEST", session=self.session)
        self.dispatcher = create_dispatcher(service, Config(bot_token="42:TEST",
                                                            admin_ids=admin_ids))
        self._update_ids = itertools.count(1)
        self.last_markup = None

    def _user(self, user_id: int) -> User:
        return User(id=user_id, is_bot=False, first_name="Тест", last_name=str(user_id))

    async def send(self, text: str, user_id: int = USER_ID) -> list[str]:
        message = Message(message_id=next(self._update_ids), date=datetime.now(),
                          chat=Chat(id=user_id, type="private"), from_user=self._user(user_id),
                          text=text)
        return await self._feed(Update(update_id=next(self._update_ids), message=message))

    async def click(self, data: str, user_id: int = USER_ID) -> list[str]:
        message = Message(message_id=1, date=datetime.now(),
                          chat=Chat(id=user_id, type="private"), text="кнопки")
        callback = CallbackQuery(id=str(next(self._update_ids)), from_user=self._user(user_id),
                                 chat_instance="test", data=data, message=message)
        return await self._feed(Update(update_id=next(self._update_ids), callback_query=callback))

    async def _feed(self, update: Update) -> list[str]:
        start = len(self.session.requests)
        await self.dispatcher.feed_update(self.bot, update)
        replies = []
        for method in self.session.requests[start:]:
            if isinstance(method, (SendMessage, EditMessageText)):
                replies.append(method.text)
                if method.reply_markup is not None:
                    self.last_markup = method.reply_markup
            elif isinstance(method, AnswerCallbackQuery) and method.text:
                replies.append(method.text)
        return replies

    def buttons(self) -> list[tuple[str, str]]:
        markup = self.last_markup
        rows = getattr(markup, "inline_keyboard", None) or []
        return [(button.text, button.callback_data) for row in rows for button in row]
