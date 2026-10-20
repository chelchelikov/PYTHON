"""Публикация событий в брокер сообщений (RabbitMQ) или в память (тесты, локальный запуск)."""

import json
import logging
from typing import Protocol

log = logging.getLogger("order-service.events")

EXCHANGE = "restaurant.events"


class EventPublisher(Protocol):
    async def publish(self, routing_key: str, payload: dict) -> None: ...


class InMemoryPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def publish(self, routing_key: str, payload: dict) -> None:
        self.events.append((routing_key, payload))
        log.info("Событие %s (in-memory): %s", routing_key, payload)


class RabbitMQPublisher:
    def __init__(self, url: str) -> None:
        self.url = url
        self._connection = None
        self._exchange = None

    async def _ensure(self):
        if self._exchange is None:
            import aio_pika

            self._connection = await aio_pika.connect_robust(self.url)
            channel = await self._connection.channel()
            self._exchange = await channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC,
                                                            durable=True)
        return self._exchange

    async def publish(self, routing_key: str, payload: dict) -> None:
        import aio_pika

        exchange = await self._ensure()
        message = aio_pika.Message(json.dumps(payload, ensure_ascii=False).encode(),
                                   content_type="application/json",
                                   delivery_mode=aio_pika.DeliveryMode.PERSISTENT)
        await exchange.publish(message, routing_key=routing_key)
        log.info("Событие %s отправлено в RabbitMQ: order_id=%s", routing_key,
                 payload.get("order_id"))

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
