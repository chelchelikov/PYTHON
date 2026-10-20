"""Подписчик RabbitMQ: получает события заказов и создаёт/отменяет доставки."""

import asyncio
import json
import logging
from collections.abc import Callable

log = logging.getLogger("delivery-service.consumer")

EXCHANGE = "restaurant.events"
QUEUE = "delivery-service.order-events"


async def consume(url: str, handler: Callable[[str, dict], None],
                  stop: asyncio.Event) -> None:
    import aio_pika

    while not stop.is_set():
        try:
            connection = await aio_pika.connect_robust(url)
            break
        except Exception as error:  # брокер ещё не запустился
            log.warning("RabbitMQ недоступен (%s), повтор через 3 с", error)
            await asyncio.sleep(3)
    else:
        return
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        exchange = await channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC,
                                                  durable=True)
        queue = await channel.declare_queue(QUEUE, durable=True)
        await queue.bind(exchange, routing_key="order.*")
        log.info("Подписка на %s (order.*) оформлена", QUEUE)
        async with queue.iterator() as messages:
            async for message in messages:
                try:
                    payload = json.loads(message.body)
                    log.info("Получено событие %s: order_id=%s", message.routing_key,
                             payload.get("order_id"))
                    await asyncio.to_thread(handler, message.routing_key, payload)
                except (ValueError, KeyError) as error:
                    # Некорректное сообщение: повтор не поможет — отбрасываем
                    log.error("Некорректное событие отброшено: %s", error)
                    await message.reject(requeue=False)
                except Exception:
                    # Временная проблема (например, БД): вернуть сообщение в очередь
                    log.exception("Ошибка обработки, сообщение вернётся в очередь")
                    await asyncio.sleep(1)
                    await message.nack(requeue=True)
                else:
                    await message.ack()
                if stop.is_set():
                    break
