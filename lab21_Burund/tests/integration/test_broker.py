"""Публикация и получение события через настоящий RabbitMQ (пропускается без брокера)."""

import asyncio
import os
import socket

import pytest

from app.events.broker import RabbitMQPublisher
from app.worker import consume

BROKER_URL = os.getenv("TEST_BROKER_URL", "amqp://guest:guest@localhost:5672/")
pytestmark = pytest.mark.integration


def broker_available() -> bool:
    try:
        socket.create_connection(("localhost", 5672), timeout=1).close()
        return True
    except OSError:
        return False


@pytest.mark.skipif(not broker_available(), reason="RabbitMQ не запущен")
def test_event_goes_through_rabbitmq():
    received: list[tuple[str, dict]] = []

    async def scenario():
        consumer = asyncio.create_task(consume(BROKER_URL, lambda t, p: received.append((t, p))))
        await asyncio.sleep(1)  # очередь объявлена и привязана
        publisher = RabbitMQPublisher(BROKER_URL)
        await publisher.publish("order.created", {"order_id": 4242, "items": 2})
        for _ in range(50):
            if any(p.get("order_id") == 4242 for _, p in received):
                break
            await asyncio.sleep(0.1)
        await publisher.close()
        consumer.cancel()

    asyncio.run(scenario())
    assert ("order.created", {"order_id": 4242, "items": 2}) in received
