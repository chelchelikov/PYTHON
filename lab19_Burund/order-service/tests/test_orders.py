import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.events import InMemoryPublisher
from app.main import create_app
from app.menu_client import MenuClient
from app.resilience import CircuitBreaker, ServiceUnavailable, State, TransientHTTPError, retry

MENU = {1: {"id": 1, "name": "Борщ", "category": "soup", "price": 350.0, "is_available": True},
        2: {"id": 2, "name": "Чизкейк", "category": "dessert", "price": 380.0,
            "is_available": True},
        3: {"id": 3, "name": "Тирамису", "category": "dessert", "price": 420.0,
            "is_available": False}}

ORDER = {"customer_name": "Бурунд", "phone": "+79001234567", "address": "ул. Ленина, 1",
         "items": [{"dish_id": 1, "quantity": 2}, {"dish_id": 2, "quantity": 1}]}


def menu_transport(fail_first: int = 0, down: bool = False):
    """Фальшивый Menu Service: первые fail_first запросов отвечают 503."""
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if down:
            raise httpx.ConnectError("connection refused", request=request)
        if calls["count"] <= fail_first:
            return httpx.Response(503, json={"detail": "temporary"})
        ids = [int(x) for x in request.url.params["ids"].split(",")]
        return httpx.Response(200, json=[MENU[i] for i in ids if i in MENU])

    return httpx.MockTransport(handler), calls


def make_client(transport, breaker=None):
    publisher = InMemoryPublisher()
    menu = MenuClient("http://menu", transport=transport, delay=0.01, breaker=breaker)
    app = create_app("sqlite://", menu_client=menu, publisher=publisher)
    return TestClient(app), publisher


# --- unit: Retry и Circuit Breaker ---
def test_retry_succeeds_after_transient_errors():
    attempts = {"n": 0}

    async def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise TransientHTTPError("503")
        return "ok"

    assert asyncio.run(retry(flaky, attempts=3, delay=0)) == "ok"
    assert attempts["n"] == 3


def test_retry_gives_up():
    async def broken():
        raise httpx.ConnectError("down")

    with pytest.raises(ServiceUnavailable):
        asyncio.run(retry(broken, attempts=2, delay=0))


def test_circuit_breaker_open_half_open_closed():
    now = {"t": 0.0}
    breaker = CircuitBreaker("menu", failure_threshold=2, recovery_timeout=10,
                             clock=lambda: now["t"])

    async def fail():
        raise ServiceUnavailable("down")

    async def ok():
        return "ok"

    for _ in range(2):
        with pytest.raises(ServiceUnavailable):
            asyncio.run(breaker.call(fail))
    assert breaker.state == State.OPEN
    with pytest.raises(ServiceUnavailable, match="OPEN"):
        asyncio.run(breaker.call(ok))  # запрос даже не выполняется
    now["t"] = 11
    assert breaker.state == State.HALF_OPEN
    assert asyncio.run(breaker.call(ok)) == "ok"
    assert breaker.state == State.CLOSED


def test_half_open_failure_reopens():
    now = {"t": 0.0}
    breaker = CircuitBreaker("menu", failure_threshold=1, recovery_timeout=5,
                             clock=lambda: now["t"])

    async def fail():
        raise ServiceUnavailable("down")

    with pytest.raises(ServiceUnavailable):
        asyncio.run(breaker.call(fail))
    now["t"] = 6
    with pytest.raises(ServiceUnavailable):
        asyncio.run(breaker.call(fail))
    assert breaker.state == State.OPEN


def test_event_payload_contains_delivery_data():
    from app.models import Order, OrderItem
    from app.service import OrderService
    order = Order(id=7, customer_name="А", phone="1", address="ул.", total=700,
                  items=[OrderItem(dish_id=1, name="Борщ", price=350, quantity=2)])
    payload = OrderService.event_payload(order)
    assert payload["event"] == "OrderCreated" and payload["order_id"] == 7
    assert payload["items"] == [{"dish_id": 1, "name": "Борщ", "quantity": 2}]


# --- integration и межсервисное взаимодействие ---
def test_create_order_calls_menu_and_publishes_event():
    transport, calls = menu_transport()
    client, publisher = make_client(transport)
    with client:
        response = client.post("/orders", json=ORDER, headers={"X-Request-ID": "abc"})
        assert response.status_code == 201
        order = response.json()
        assert order["total"] == 350 * 2 + 380
        assert calls["count"] == 1
        routing_key, payload = publisher.events[0]
        assert routing_key == "order.created" and payload["order_id"] == order["id"]
        assert client.get(f"/orders/{order['id']}").json()["items"][0]["name"] == "Борщ"


def test_order_crud_and_cancel_event():
    transport, _ = menu_transport()
    client, publisher = make_client(transport)
    with client:
        order_id = client.post("/orders", json=ORDER).json()["id"]
        updated = client.put(f"/orders/{order_id}", json={
            "customer_name": "Бурунд", "phone": "+79001234567", "address": "ул. Мира, 5",
            "status": "cooking"}).json()
        assert updated["address"] == "ул. Мира, 5" and updated["status"] == "cooking"
        assert client.delete(f"/orders/{order_id}").json()["status"] == "cancelled"
        assert publisher.events[-1][0] == "order.cancelled"
        assert client.delete(f"/orders/{order_id}").status_code == 409
        assert client.get("/orders/999").status_code == 404


def test_rejected_orders():
    transport, _ = menu_transport()
    client, publisher = make_client(transport)
    with client:
        bad = {**ORDER, "items": [{"dish_id": 3, "quantity": 1}]}
        assert client.post("/orders", json=bad).status_code == 409   # недоступно
        bad = {**ORDER, "items": [{"dish_id": 42, "quantity": 1}]}
        assert client.post("/orders", json=bad).status_code == 409   # нет в меню
        assert client.post("/orders", json={**ORDER, "items": []}).status_code == 422
        assert publisher.events == []


def test_retry_on_temporary_menu_failure():
    transport, calls = menu_transport(fail_first=2)
    client, _ = make_client(transport)
    with client:
        assert client.post("/orders", json=ORDER).status_code == 201
        assert calls["count"] == 3  # две неудачи + успешный повтор


def test_menu_unavailable_opens_circuit():
    transport, calls = menu_transport(down=True)
    breaker = CircuitBreaker("menu-service", failure_threshold=2, recovery_timeout=60)
    client, publisher = make_client(transport, breaker)
    with client:
        for _ in range(2):
            response = client.post("/orders", json=ORDER)
            assert response.status_code == 503
        assert calls["count"] == 6  # 2 запроса × 3 попытки
        response = client.post("/orders", json=ORDER)
        assert response.status_code == 503 and "OPEN" in response.json()["detail"]
        assert calls["count"] == 6  # Circuit Breaker не пустил запрос к Menu Service
        assert client.get("/health").json()["menu_circuit"] == "open"
        assert publisher.events == []
