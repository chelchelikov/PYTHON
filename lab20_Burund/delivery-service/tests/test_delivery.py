import pytest
from fastapi.testclient import TestClient

from app.database import Database
from app.main import create_app
from app.schemas import DeliveryIn, DeliveryStatus, DeliveryUpdate
from app.service import DeliveryConflict, DeliveryNotFound, DeliveryService

# Событие в том формате, который публикует Order Service
ORDER_CREATED = {
    "event": "OrderCreated",
    "order_id": 15,
    "customer_name": "Бурунд",
    "phone": "+79001234567",
    "address": "ул. Ленина, 1",
    "total": 1080.0,
    "items": [
        {"dish_id": 1, "name": "Борщ", "quantity": 2},
        {"dish_id": 2, "name": "Чизкейк", "quantity": 1},
    ],
}


@pytest.fixture
def service():
    db = Database("sqlite://")
    db.create_tables()
    session = db.session_factory()
    yield DeliveryService(session)
    session.close()


def make(service, order_id: int) -> object:
    return service.create(
        DeliveryIn(
            order_id=order_id,
            customer_name="Гость",
            phone="12345",
            address="ул. Мира, 1",
            order_total=500,
        )
    )


# --- unit ---
def test_create_assigns_courier_and_eta(service):
    delivery = service.create(
        DeliveryIn(
            order_id=1, customer_name="Гость", phone="12345", address="ул. Мира, 1", order_total=500
        ),
        items_count=3,
    )
    assert delivery.courier == "Алексей"
    assert delivery.eta_minutes == 30 + 5 * 3
    assert delivery.status == DeliveryStatus.assigned.value


def test_couriers_are_balanced(service):
    couriers = [make(service, order_id).courier for order_id in range(1, 6)]
    assert couriers == ["Алексей", "Мария", "Тимур", "Ольга", "Алексей"]


def test_duplicate_order_conflict(service):
    make(service, 1)
    with pytest.raises(DeliveryConflict):
        make(service, 1)


def test_update_and_finished_delivery_is_locked(service):
    delivery = make(service, 1)
    update = DeliveryUpdate(
        address="ул. Новая, 2", courier="Мария", status="delivered", eta_minutes=0
    )
    assert service.update(delivery.id, update).status == "delivered"
    with pytest.raises(DeliveryConflict):
        service.update(delivery.id, update)


def test_delete_and_not_found(service):
    delivery = make(service, 1)
    service.delete(delivery.id)
    with pytest.raises(DeliveryNotFound):
        service.get(delivery.id)
    with pytest.raises(DeliveryNotFound):
        service.by_order(1)


# --- обработка событий (взаимодействие с Order Service через брокер) ---
def test_order_created_event_creates_delivery_idempotently(service):
    first = service.handle_event("order.created", ORDER_CREATED)
    again = service.handle_event("order.created", ORDER_CREATED)  # повторная доставка события
    assert first.id == again.id
    assert first.order_total == 1080.0 and first.eta_minutes == 30 + 5 * 3
    assert len(service.list()) == 1


def test_order_cancelled_event(service):
    service.handle_event("order.created", ORDER_CREATED)
    delivery = service.handle_event("order.cancelled", {"order_id": 15})
    assert delivery.status == "cancelled"
    assert service.handle_event("order.cancelled", {"order_id": 999}) is None
    assert service.handle_event("order.unknown", {}) is None


# --- integration (HTTP + БД) ---
def test_api_crud_and_event_handler():
    with TestClient(create_app("sqlite://", broker_url="")) as client:
        client.app.state.handle_event("order.created", ORDER_CREATED)  # как из consumer
        delivery = client.get("/deliveries/by-order/15").json()
        assert delivery["customer_name"] == "Бурунд"
        response = client.put(
            f"/deliveries/{delivery['id']}",
            json={
                "address": "ул. Ленина, 1",
                "courier": "Ольга",
                "status": "on_the_way",
                "eta_minutes": 20,
            },
        )
        assert response.json()["status"] == "on_the_way"
        assert client.get("/deliveries?status=on_the_way").json()[0]["id"] == delivery["id"]
        assert client.delete(f"/deliveries/{delivery['id']}").status_code == 204


def test_api_errors_and_health():
    with TestClient(create_app("sqlite://", broker_url="")) as client:
        assert client.get("/deliveries/1").status_code == 404
        payload = {
            "order_id": 1,
            "customer_name": "Гость",
            "phone": "12345",
            "address": "ул. Мира, 1",
            "order_total": 100,
        }
        assert client.post("/deliveries", json=payload).status_code == 201
        assert client.post("/deliveries", json=payload).status_code == 409
        assert client.post("/deliveries", json={**payload, "phone": "1"}).status_code == 422
        assert client.get("/health").json()["status"] == "healthy"


def test_consumer_survives_unavailable_broker(monkeypatch):
    import asyncio

    import aio_pika

    from app.consumer import consume

    attempts = {"n": 0}
    stop = asyncio.Event()

    async def refuse(url):
        attempts["n"] += 1
        stop.set()  # после первой неудачной попытки просим consumer остановиться
        raise ConnectionError("broker is down")

    async def no_sleep(_):
        return None

    monkeypatch.setattr(aio_pika, "connect_robust", refuse)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    asyncio.run(consume("amqp://broker", lambda *_: None, stop))  # не падает
    assert attempts["n"] == 1
