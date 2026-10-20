import asyncio

import pytest

from app.events.broker import LocalPublisher
from app.events.relay import relay_once
from app.worker import make_handler
from tests.conftest import USER, token_for

pytestmark = pytest.mark.integration
ORDER = {
    "address": "ул. Ленина, 1",
    "items": [{"dish_id": 5, "quantity": 1}, {"dish_id": 10, "quantity": 2}],
}


def test_register_login_me(client):
    created = client.post("/auth/register", json=USER)
    assert created.status_code == 201 and created.json()["role"] == "user"
    assert "password" not in created.text
    headers = token_for(client, USER["email"], USER["password"])
    assert client.get("/auth/me", headers=headers).json()["email"] == USER["email"]
    form = client.post(
        "/auth/token", data={"username": USER["email"], "password": USER["password"]}
    )
    assert form.status_code == 200


def test_auth_errors(client):
    client.post("/auth/register", json=USER)
    duplicate = client.post("/auth/register", json=USER)
    assert duplicate.status_code == 409 and duplicate.json()["error"] == "EMAIL_TAKEN"
    wrong = client.post("/auth/login", json={"email": USER["email"], "password": "bad12345"})
    assert wrong.status_code == 401
    invalid = client.post("/auth/register", json={**USER, "email": "not-an-email"})
    assert invalid.status_code == 422 and invalid.json()["error"] == "VALIDATION_ERROR"
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_menu_filters_sort_and_cache(client, admin_headers):
    first = client.get("/dishes", params={"category": "main", "sort": "-price"})
    assert first.headers["X-Cache"] == "MISS"
    assert [d["name"] for d in first.json()["items"]] == [
        "Стейк рибай",
        "Лосось на гриле",
        "Паста карбонара",
    ]
    assert (
        client.get("/dishes", params={"category": "main", "sort": "-price"}).headers["X-Cache"]
        == "HIT"
    )
    client.patch("/dishes/5", json={"price": 1990}, headers=admin_headers)
    after = client.get("/dishes", params={"category": "main", "sort": "-price"})
    assert after.headers["X-Cache"] == "MISS" and after.json()["items"][0]["price"] == 1990
    found = client.get("/dishes", params={"q": "салат"}).json()
    assert [d["name"] for d in found["items"]] == ["Греческий салат"]
    assert client.get("/dishes", params={"max_price": 200}).json()["total"] == 1


def test_dish_admin_crud_and_permissions(client, admin_headers, user_headers):
    dish = {"name": "Окрошка", "category": "soup", "price": 330}
    assert client.post("/dishes", json=dish).status_code == 401
    forbidden = client.post("/dishes", json=dish, headers=user_headers)
    assert forbidden.status_code == 403 and forbidden.json()["error"] == "ADMIN_ONLY"
    created = client.post("/dishes", json=dish, headers=admin_headers)
    assert created.status_code == 201
    dish_id = created.json()["id"]
    assert client.post("/dishes", json=dish, headers=admin_headers).status_code == 409
    replaced = client.put(f"/dishes/{dish_id}", json={**dish, "price": 340}, headers=admin_headers)
    assert replaced.json()["price"] == 340
    assert client.delete(f"/dishes/{dish_id}", headers=admin_headers).status_code == 204
    assert client.get(f"/dishes/{dish_id}").json()["error"] == "DISH_NOT_FOUND"


def test_full_order_cycle(client, db, user_headers, admin_headers):
    created = client.post("/orders", json=ORDER, headers=user_headers)
    assert created.status_code == 201
    order = created.json()
    assert order["items_total"] == 1890 + 2 * 190 and order["delivery_fee"] == 0
    assert order["delivery"]["status"] == "pending"
    assert {i["dish_name"] for i in order["items"]} == {"Стейк рибай", "Морс клюквенный"}

    # фоновый worker: outbox → событие → назначение курьера
    asyncio.run(relay_once(db.session_factory, LocalPublisher(make_handler(db))))
    delivery = client.get(f"/orders/{order['id']}", headers=user_headers).json()["delivery"]
    assert delivery["status"] == "assigned" and delivery["courier"] == "Алексей"

    for status in ("cooking", "ready"):
        response = client.patch(
            f"/orders/{order['id']}/status", json={"status": status}, headers=admin_headers
        )
        assert response.json()["status"] == status
    client.patch(
        f"/deliveries/{delivery['id']}", json={"status": "delivered"}, headers=admin_headers
    )
    final = client.get(f"/orders/{order['id']}", headers=user_headers).json()
    assert final["status"] == "delivered" and final["delivery"]["status"] == "delivered"
    stats = client.get("/stats", headers=admin_headers).json()
    assert stats["orders"] == 1 and stats["revenue"] == 2270


def test_order_errors_and_access(client, user_headers, admin_headers):
    assert client.post("/orders", json=ORDER).status_code == 401
    small = client.post(
        "/orders", json={**ORDER, "items": [{"dish_id": 10, "quantity": 1}]}, headers=user_headers
    )
    assert small.status_code == 422 and small.json()["error"] == "ORDER_TOO_SMALL"
    duplicate_items = {**ORDER, "items": [{"dish_id": 5, "quantity": 1}] * 2}
    assert client.post("/orders", json=duplicate_items, headers=user_headers).status_code == 422
    assert client.get("/orders/999", headers=user_headers).status_code == 404

    order_id = client.post("/orders", json=ORDER, headers=user_headers).json()["id"]
    client.post("/auth/register", json={**USER, "email": "petr@test.ru"})
    stranger = token_for(client, "petr@test.ru", USER["password"])
    assert client.get(f"/orders/{order_id}", headers=stranger).status_code == 403
    assert client.get("/orders", headers=stranger).json() == []
    assert len(client.get("/orders", headers=admin_headers).json()) == 1
    assert (
        client.patch(
            f"/orders/{order_id}/status", json={"status": "cooking"}, headers=user_headers
        ).status_code
        == 403
    )


def test_cancel_returns_portions_to_menu(client, user_headers):
    before = client.get("/dishes/5").json()["portions_available"]
    order_id = client.post("/orders", json=ORDER, headers=user_headers).json()["id"]
    assert client.get("/dishes/5").json()["portions_available"] == before - 1
    cancelled = client.post(f"/orders/{order_id}/cancel", headers=user_headers).json()
    assert cancelled["status"] == "cancelled"
    assert client.get("/dishes/5").json()["portions_available"] == before
    again = client.post(f"/orders/{order_id}/cancel", headers=user_headers)
    assert again.status_code == 422 and again.json()["error"] == "CANNOT_CANCEL"


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "healthy" and body["database"] == "healthy"
    assert body["outbox_backlog"] == 0


def test_admin_from_settings_can_login(client):
    # администратор создаётся при запуске из ADMIN_EMAIL / ADMIN_PASSWORD
    response = client.post("/auth/login", json={"email": "admin@test.ru", "password": "admin12345"})
    assert response.status_code == 200
    me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"}
    )
    assert me.json()["role"] == "admin"
