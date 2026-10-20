import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from app.cache import MenuCache
from app.core.errors import BusinessRuleError
from app.events.broker import LocalPublisher
from app.events.relay import relay_once
from app.models import DeliveryStatus, OrderStatus, OutboxEvent
from app.schemas.order import DeliveryPatch, OrderIn
from app.services.delivery_service import DeliveryService
from app.services.order_service import OrderService


def make_order(session, user, dish_id=5, quantity=1):
    order_in = OrderIn(address="ул. Мира, 5", items=[{"dish_id": dish_id, "quantity": quantity}])
    return OrderService(session, Mock()).create(user, order_in)


def handler_for(db):
    def handle(event_type, payload):
        with db.session_factory() as s:
            DeliveryService(s).handle_event(event_type, payload)

    return handle


def test_assign_balances_couriers_and_is_idempotent(session, user):
    service = DeliveryService(session)
    orders = [make_order(session, user) for _ in range(3)]
    couriers = [service.assign(o.id, 1).courier for o in orders]
    assert couriers == ["Алексей", "Мария", "Тимур"]
    again = service.assign(orders[0].id, 1)  # повторное событие
    assert again.courier == "Алексей" and again.eta_minutes == 35


def test_delivery_update_syncs_order_status(session, user):
    order = make_order(session, user)
    service = DeliveryService(session)
    delivery = service.assign(order.id, 1)
    service.update(delivery.id, DeliveryPatch(status=DeliveryStatus.ON_THE_WAY))
    assert order.status == OrderStatus.DELIVERING
    service.update(delivery.id, DeliveryPatch(status=DeliveryStatus.DELIVERED))
    assert order.status == OrderStatus.DELIVERED
    with pytest.raises(BusinessRuleError):
        service.update(delivery.id, DeliveryPatch(courier="Ольга"))


def test_relay_publishes_outbox_events(db, session, user):
    order = make_order(session, user, quantity=2)
    sent = asyncio.run(relay_once(db.session_factory, LocalPublisher(handler_for(db))))
    assert sent == 1
    session.expire_all()
    assert order.delivery.status == DeliveryStatus.ASSIGNED
    assert session.query(OutboxEvent).one().published_at is not None
    assert asyncio.run(relay_once(db.session_factory, LocalPublisher(handler_for(db)))) == 0


def test_relay_keeps_events_when_broker_is_down(db, session, user):
    make_order(session, user)
    broken = Mock()
    broken.publish = AsyncMock(side_effect=ConnectionError("broker down"))
    assert asyncio.run(relay_once(db.session_factory, broken)) == 0
    broken.publish.assert_awaited_once()
    session.expire_all()
    event = session.query(OutboxEvent).one()
    assert event.published_at is None and event.attempts == 1  # будет отправлено позже


def test_cache_survives_redis_failure():
    client = Mock()
    client.get.side_effect = ConnectionError("redis down")
    client.set.side_effect = ConnectionError("redis down")
    client.scan_iter.side_effect = ConnectionError("redis down")
    client.ping.side_effect = ConnectionError("redis down")
    cache = MenuCache(client)
    assert cache.get("k") is None
    cache.set("k", {"a": 1})
    cache.invalidate()
    assert cache.ping() == "unavailable"
    assert MenuCache(None).ping() == "disabled"
