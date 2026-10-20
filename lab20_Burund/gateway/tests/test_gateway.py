import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import Backend, create_app
from app.resilience import CircuitBreaker


def backends(timeout: float = 60):
    return {
        key: Backend(
            name,
            f"http://{name}",
            prefix,
            CircuitBreaker(name, failure_threshold=2, recovery_timeout=timeout),
        )
        for key, name, prefix in [
            ("menu", "menu-service", "dishes"),
            ("orders", "order-service", "orders"),
            ("deliveries", "delivery-service", "deliveries"),
        ]
    }


class FakeCluster:
    """Фальшивые сервисы: можно «выключить» любой из них."""

    def __init__(self) -> None:
        self.down: set[str] = set()
        self.calls: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        self.calls.append(f"{request.method} {host}{path}")
        if host in self.down:
            raise httpx.ConnectError("connection refused", request=request)
        if path == "/health":
            return httpx.Response(200, json={"status": "healthy"})
        if host == "menu-service" and path == "/dishes":
            return httpx.Response(200, json=[{"id": 1, "name": "Борщ"}])
        if (
            host == "order-service"
            and path == "/orders"
            and request.method == "POST"
            and "menu-service" in self.down
        ):
            return httpx.Response(503, json={"detail": "menu-service: сервис недоступен"})
        if host == "order-service" and path == "/orders" and request.method == "POST":
            return httpx.Response(201, json={"id": 5, **json.loads(request.content)})
        if host == "order-service" and path == "/orders/5":
            return httpx.Response(200, json={"id": 5, "status": "created"})
        if host == "delivery-service" and path == "/deliveries/by-order/5":
            return httpx.Response(200, json={"order_id": 5, "courier": "Мария"})
        return httpx.Response(404, json={"detail": "not found"})


@pytest.fixture
def cluster():
    return FakeCluster()


@pytest.fixture
def client(cluster):
    app = create_app(backends(), transport=httpx.MockTransport(cluster.handler), retry_delay=0)
    with TestClient(app) as test_client:
        yield test_client


def test_routes_to_menu(client, cluster):
    response = client.get("/api/dishes", headers={"X-Request-ID": "r1"})
    assert response.json() == [{"id": 1, "name": "Борщ"}]
    assert response.headers["X-Request-ID"] == "r1"
    assert cluster.calls == ["GET menu-service/dishes"]


def test_post_is_forwarded_with_body(client):
    response = client.post("/api/orders", json={"customer_name": "Бурунд"})
    assert response.status_code == 201
    assert response.json()["customer_name"] == "Бурунд"


def test_backend_404_is_passed_through(client):
    assert client.get("/api/deliveries/77").status_code == 404


def test_composition_order_with_delivery(client, cluster):
    data = client.get("/api/orders/5/full").json()
    assert data["order"]["id"] == 5 and data["delivery"]["courier"] == "Мария"
    cluster.down.add("delivery-service")
    data = client.get("/api/orders/5/full").json()
    assert data["delivery"] == "delivery-service недоступен"  # частичный ответ


def test_health_reports_each_service(client, cluster):
    assert client.get("/health").json()["status"] == "healthy"
    cluster.down.add("order-service")
    health = client.get("/health").json()
    assert health["status"] == "degraded"
    assert health["services"]["order-service"]["status"] == "unavailable"
    assert health["services"]["menu-service"]["status"] == "healthy"


def test_unavailable_service_opens_circuit(client, cluster):
    cluster.down.add("menu-service")
    for _ in range(2):
        assert client.get("/api/dishes").status_code == 503
    assert len(cluster.calls) == 6  # GET повторяется 3 раза
    response = client.get("/api/dishes")
    assert response.status_code == 503 and response.json()["circuit"] == "open"
    assert len(cluster.calls) == 6  # запрос не отправлялся
    assert client.get("/api/orders/5").status_code == 200  # другие сервисы работают


def test_post_is_not_retried(client, cluster):
    cluster.down.add("order-service")
    assert client.post("/api/orders", json={}).status_code == 503
    assert cluster.calls == ["POST order-service/orders"]


def test_dependency_failure_does_not_open_neighbour_circuit(client, cluster):
    # Меню упало: order-service жив и сам отвечает 503 — его Circuit Breaker не размыкается
    cluster.down.add("menu-service")
    for _ in range(3):
        response = client.post("/api/orders", json={"customer_name": "Бурунд"})
        assert response.status_code == 503
        assert "menu-service" in response.json()["detail"]
    assert client.app.state.backends["orders"].breaker.state.value == "closed"
    assert client.get("/api/orders/5").status_code == 200
