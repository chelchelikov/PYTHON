from unittest.mock import Mock

import pytest

from app.core.errors import BusinessRuleError, ForbiddenError, NotFoundError
from app.models import DeliveryStatus, Dish, OrderStatus, OutboxEvent
from app.schemas.auth import RegisterIn
from app.schemas.order import OrderIn
from app.services.auth_service import AuthService
from app.services.order_service import DELIVERY_FEE, FREE_DELIVERY_FROM, OrderService, delivery_fee
from tests.conftest import SECRET

ADDRESS = "ул. Ленина, 1"


def order_in(*items: tuple[int, int]) -> OrderIn:
    return OrderIn(address=ADDRESS, items=[{"dish_id": d, "quantity": q} for d, q in items])


@pytest.fixture
def cache_mock():
    return Mock()


@pytest.fixture
def service(session, cache_mock):
    return OrderService(session, cache_mock)


@pytest.mark.parametrize(
    "items_total, fee",
    [
        (500, DELIVERY_FEE),
        (1999.99, DELIVERY_FEE),
        (FREE_DELIVERY_FROM, 0),
        (5000, 0),
    ],
)
def test_delivery_fee(items_total, fee):
    assert delivery_fee(items_total) == fee


def test_create_order_writes_items_delivery_and_outbox(service, session, user, cache_mock):
    order = service.create(user, order_in((3, 2)))  # борщ 350 × 2
    assert order.items_total == 700 and order.total == 700 + DELIVERY_FEE
    assert order.delivery.status == DeliveryStatus.PENDING
    assert session.get(Dish, 3).portions_available == 28
    event = session.query(OutboxEvent).one()
    assert event.event_type == "order.created" and event.payload["order_id"] == order.id
    cache_mock.invalidate.assert_called_once()


def test_free_delivery_for_big_order(service, user):
    order = service.create(user, order_in((5, 2)))  # рибай 1890 × 2
    assert order.delivery_fee == 0 and order.total == 3780


@pytest.mark.parametrize(
    "portions, items, error_code",
    [
        (30, ((3, 1),), "ORDER_TOO_SMALL"),  # 350 ₽ < 500 ₽
        (2, ((3, 3),), "NOT_ENOUGH_PORTIONS"),  # осталось 2 порции, просят 3
        (
            2,
            ((5, 1), (3, 3)),
            "NOT_ENOUGH_PORTIONS",
        ),  # первое блюдо есть — заказ всё равно отклонён
    ],
)
def test_business_rules_on_create(service, user, session, portions, items, error_code):
    session.get(Dish, 3).portions_available = portions
    session.commit()
    with pytest.raises(BusinessRuleError) as error:
        service.create(user, order_in(*items))
    assert error.value.code == error_code
    session.rollback()
    assert session.get(Dish, 3).portions_available == portions  # ничего не списано
    assert session.get(Dish, 5).portions_available == 30


def test_unavailable_and_missing_dish(service, user, session):
    session.get(Dish, 5).is_available = False
    session.commit()
    with pytest.raises(BusinessRuleError, match="снято с продажи"):
        service.create(user, order_in((5, 1)))
    session.rollback()
    with pytest.raises(NotFoundError):
        service.create(user, order_in((999, 1)))


def test_cancel_restores_portions_and_locks_order(service, user, session):
    order = service.create(user, order_in((3, 2)))
    cancelled = service.cancel(user, order.id)
    assert cancelled.status == OrderStatus.CANCELLED
    assert cancelled.delivery.status == DeliveryStatus.CANCELLED
    assert session.get(Dish, 3).portions_available == 30
    with pytest.raises(BusinessRuleError):
        service.cancel(user, order.id)


def test_status_transitions(service, user, admin):
    order = service.create(user, order_in((5, 1)))
    with pytest.raises(BusinessRuleError, match="Нельзя перейти"):
        service.change_status(order.id, OrderStatus.DELIVERED, admin)
    for status in (
        OrderStatus.COOKING,
        OrderStatus.READY,
        OrderStatus.DELIVERING,
        OrderStatus.DELIVERED,
    ):
        order = service.change_status(order.id, status, admin)
    assert order.delivery.status == DeliveryStatus.DELIVERED
    with pytest.raises(BusinessRuleError):
        service.cancel(user, order.id)  # доставленный заказ не отменить


def test_user_cannot_access_foreign_order(service, user, session):
    stranger = AuthService(session, SECRET, 60).register(
        RegisterIn(
            email="other@test.ru", full_name="Другой", phone="+79009998877", password="other1234"
        )
    )
    order = service.create(user, order_in((5, 1)))
    with pytest.raises(ForbiddenError):
        service.get(stranger, order.id)
    assert service.find(stranger, None, True, 10, 0) == []


def test_delete_only_finished_orders(service, user, admin):
    order = service.create(user, order_in((5, 1)))
    with pytest.raises(BusinessRuleError):
        service.delete(admin, order.id)
    service.cancel(admin, order.id)
    service.delete(admin, order.id)
    with pytest.raises(NotFoundError):
        service.get(admin, order.id)
