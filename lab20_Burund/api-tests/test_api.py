"""Автоматическая проверка API запущенной системы через gateway.

Запуск: docker compose --profile test run --rm api-tests
или локально: GATEWAY_URL=http://localhost:8000 pytest api-tests
"""

import os
import time
import uuid

import httpx
import pytest

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
CUSTOMER = {"customer_name": "API-тест", "phone": "+79000000000", "address": "ул. Тестовая, 1"}


@pytest.fixture(scope="module")
def api():
    with httpx.Client(base_url=GATEWAY_URL, timeout=10) as client:
        deadline = time.monotonic() + 60
        while True:  # ждём готовности всей системы
            try:
                if client.get("/health").json().get("status") == "healthy":
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline:
                pytest.fail("Система не стала healthy за 60 секунд")
            time.sleep(2)
        yield client


def wait_for(fetch, condition, timeout: float = 15):
    """Асинхронные события обрабатываются не мгновенно — опрашиваем до таймаута."""
    deadline = time.monotonic() + timeout
    while True:
        value = fetch()
        if condition(value):
            return value
        if time.monotonic() > deadline:
            return value
        time.sleep(0.5)


@pytest.fixture
def dish(api):
    data = {"name": f"Тестовое блюдо {uuid.uuid4().hex[:8]}", "category": "main", "price": 500}
    created = api.post("/api/dishes", json=data).json()
    yield created
    api.delete(f"/api/dishes/{created['id']}")


def test_health_of_all_services(api):
    health = api.get("/health").json()
    assert health["status"] == "healthy"
    assert set(health["services"]) == {"menu-service", "order-service", "delivery-service"}


def test_request_id_is_propagated(api):
    response = api.get("/api/dishes", headers={"X-Request-ID": "api-test-42"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "api-test-42"


def test_menu_crud(api):
    data = {"name": f"Блюдо {uuid.uuid4().hex[:8]}", "category": "soup", "price": 300}
    created = api.post("/api/dishes", json=data)
    assert created.status_code == 201
    dish_id = created.json()["id"]
    assert api.get(f"/api/dishes/{dish_id}").json()["name"] == data["name"]
    patched = api.patch(f"/api/dishes/{dish_id}", json={"price": 320})
    assert patched.status_code == 200 and patched.json()["price"] == 320
    assert api.delete(f"/api/dishes/{dish_id}").status_code == 204
    assert api.get(f"/api/dishes/{dish_id}").status_code == 404


def test_validation_errors(api):
    assert api.post("/api/dishes", json={"name": "", "price": -1}).status_code == 422
    assert api.post("/api/orders", json={**CUSTOMER, "items": []}).status_code == 422
    assert api.get("/api/orders/999999").status_code == 404


def test_order_with_unknown_dish_is_rejected(api):
    response = api.post("/api/orders",
                        json={**CUSTOMER, "items": [{"dish_id": 999999, "quantity": 1}]})
    assert response.status_code == 409


def test_order_creates_delivery_via_event(api, dish):
    response = api.post("/api/orders",
                        json={**CUSTOMER, "items": [{"dish_id": dish["id"], "quantity": 2}]})
    assert response.status_code == 201
    order = response.json()
    assert order["total"] == 1000

    full = wait_for(lambda: api.get(f"/api/orders/{order['id']}/full").json(),
                    lambda data: isinstance(data.get("delivery"), dict))
    delivery = full["delivery"]
    assert delivery["order_id"] == order["id"]
    assert delivery["status"] == "assigned" and delivery["courier"]


def test_cancel_order_cancels_delivery(api, dish):
    order = api.post("/api/orders",
                     json={**CUSTOMER, "items": [{"dish_id": dish["id"], "quantity": 1}]}).json()
    wait_for(lambda: api.get(f"/api/deliveries/by-order/{order['id']}").status_code,
             lambda code: code == 200)
    cancelled = api.delete(f"/api/orders/{order['id']}")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    delivery = wait_for(lambda: api.get(f"/api/deliveries/by-order/{order['id']}").json(),
                        lambda data: data.get("status") == "cancelled")
    assert delivery["status"] == "cancelled"
