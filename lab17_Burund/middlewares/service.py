from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from services.hotel import HotelService


class ServiceMiddleware(BaseMiddleware):
    """Передаёт в обработчики сервис бизнес-логики (внедрение зависимости)."""

    def __init__(self, service: HotelService) -> None:
        self.service = service

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        data["service"] = self.service
        return await handler(event, data)
