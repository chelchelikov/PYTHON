import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

log = logging.getLogger("hotel_bot")


def describe(event: TelegramObject) -> str:
    if isinstance(event, Message):
        if event.text and event.text.startswith("/"):
            return event.text.split()[0]
        return f"text:{(event.text or event.content_type)[:30]}"
    if isinstance(event, CallbackQuery):
        return f"callback:{(event.data or '').split(':')[0]}:{(event.data or '').split(':')[1:2]}"
    return type(event).__name__


class ActivityMiddleware(BaseMiddleware):
    """Журналирование: пользователь, действие, время обработки; запись в таблицу activity."""

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        user = getattr(event, "from_user", None)
        action = describe(event)
        start = time.perf_counter()
        try:
            return await handler(event, data)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            if user is not None:
                log.info("USER %s %s (%.1f мс)", user.id, action, elapsed)
                service = data.get("service")
                if service is not None:
                    await service.log_action(user.id, action)
