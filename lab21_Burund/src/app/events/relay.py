"""Outbox relay: переносит события из таблицы outbox_events в брокер.

Если брокер недоступен, события остаются в таблице и будут отправлены позже —
заказы при этом продолжают создаваться (отказоустойчивость).
"""

import logging

from sqlalchemy.orm import sessionmaker

from app.events.broker import Publisher
from app.repositories import OutboxRepository

log = logging.getLogger("restaurant.outbox")


async def relay_once(session_factory: sessionmaker, publisher: Publisher, batch: int = 50) -> int:
    """Отправляет пачку событий. Возвращает число отправленных."""
    sent = 0
    with session_factory() as session:
        outbox = OutboxRepository(session)
        for event in outbox.pending(batch):
            try:
                await publisher.publish(event.event_type, event.payload)
            except Exception as error:
                event.attempts += 1
                session.commit()
                log.warning(
                    "Брокер недоступен, событие %s отложено (попытка %s): %s",
                    event.id,
                    event.attempts,
                    error,
                )
                break
            outbox.mark_published(event)
            session.commit()
            sent += 1
    if sent:
        log.info("Отправлено событий: %s", sent)
    return sent
