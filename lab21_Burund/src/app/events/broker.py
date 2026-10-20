"""Брокер сообщений: RabbitMQ в рабочем режиме, локальная доставка — без брокера и в тестах."""

import json
import logging
from collections.abc import Callable
from typing import Protocol

log = logging.getLogger("restaurant.broker")

EXCHANGE = "restaurant.events"
QUEUE = "delivery.assignments"


class Publisher(Protocol):
    async def publish(self, event_type: str, payload: dict) -> None: ...


class LocalPublisher:
    """Без брокера: событие сразу передаётся обработчику."""

    def __init__(self, handler: Callable[[str, dict], None]) -> None:
        self.handler = handler

    async def publish(self, event_type: str, payload: dict) -> None:
        self.handler(event_type, payload)


class RabbitMQPublisher:
    def __init__(self, url: str) -> None:
        self.url = url
        self._connection = None
        self._exchange = None

    async def _exchange_ready(self):
        if self._exchange is None:
            import aio_pika

            self._connection = await aio_pika.connect_robust(self.url, timeout=5)
            channel = await self._connection.channel()
            self._exchange = await channel.declare_exchange(
                EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
            )
        return self._exchange

    async def publish(self, event_type: str, payload: dict) -> None:
        import aio_pika

        exchange = await self._exchange_ready()
        await exchange.publish(
            aio_pika.Message(
                json.dumps(payload).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=event_type,
        )

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = self._exchange = None
