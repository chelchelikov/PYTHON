"""Фоновый worker: outbox relay + подписчик RabbitMQ, назначающий курьеров.

Запуск: python -m app.worker
"""

import asyncio
import json
import logging

from app.core.config import get_settings
from app.database import Database
from app.events.broker import EXCHANGE, QUEUE, LocalPublisher, RabbitMQPublisher
from app.events.relay import relay_once
from app.services.delivery_service import DeliveryService

log = logging.getLogger("restaurant.worker")


def make_handler(db: Database):
    def handle(event_type: str, payload: dict) -> None:
        with db.session_factory() as session:
            DeliveryService(session).handle_event(event_type, payload)

    return handle


async def relay_loop(db: Database, publisher, interval: float = 1.0) -> None:
    while True:
        try:
            await relay_once(db.session_factory, publisher)
        except Exception:
            log.exception("Ошибка outbox relay")
        await asyncio.sleep(interval)


async def consume(url: str, handler) -> None:
    import aio_pika

    while True:
        try:
            connection = await aio_pika.connect_robust(url, timeout=5)
            break
        except Exception as error:
            log.warning("RabbitMQ недоступен (%s), повтор через 3 с", error)
            await asyncio.sleep(3)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await channel.declare_queue(QUEUE, durable=True)
        await queue.bind(exchange, routing_key="order.*")
        log.info("Подписка на %s оформлена", QUEUE)
        async with queue.iterator() as messages:
            async for message in messages:
                try:
                    await asyncio.to_thread(handler, message.routing_key, json.loads(message.body))
                except (ValueError, KeyError) as error:
                    log.error("Некорректное событие отброшено: %s", error)
                    await message.reject(requeue=False)
                except Exception:
                    log.exception("Ошибка обработки, событие вернётся в очередь")
                    await asyncio.sleep(1)
                    await message.nack(requeue=True)
                else:
                    await message.ack()


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    db = Database(settings.database_url)
    db.create_tables()
    handler = make_handler(db)
    if settings.broker_url:
        log.info("Worker запущен: outbox → RabbitMQ → назначение курьеров")
        await asyncio.gather(
            relay_loop(db, RabbitMQPublisher(settings.broker_url)),
            consume(settings.broker_url, handler),
        )
    else:
        log.info("Worker запущен без брокера: события обрабатываются локально")
        await relay_loop(db, LocalPublisher(handler))


if __name__ == "__main__":
    asyncio.run(main())
