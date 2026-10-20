import pytest
from fastapi.testclient import TestClient

from app.database import Database
from app.main import create_app
from app.repository import DishRepository
from app.schemas import DishIn, DishPatch
from app.service import DishConflict, DishNotFound, MenuService


@pytest.fixture
def service():
    db = Database("sqlite://")
    db.create_tables()
    session = db.session_factory()
    menu = MenuService(DishRepository(session))
    menu.seed()
    yield menu
    session.close()


@pytest.fixture
def client():
    with TestClient(create_app("sqlite://")) as test_client:
        yield test_client


# --- unit ---
def test_seed_creates_menu_once(service):
    assert len(service.list()) == 10
    assert service.seed() == 0


def test_create_and_get(service):
    dish = service.create(DishIn(name="Окрошка", category="soup", price=330))
    assert service.get(dish.id).name == "Окрошка"


def test_duplicate_name_conflict(service):
    with pytest.raises(DishConflict):
        service.create(DishIn(name="Борщ", category="soup", price=1))


def test_filter_by_category_ids_and_availability(service):
    assert {d.name for d in service.list(category="soup")} == {"Борщ", "Том ям"}
    assert {d.id for d in service.list(ids=[1, 3, 99])} == {1, 3}  # несуществующий id пропущен
    service.patch(1, DishPatch(is_available=False))
    assert 1 not in [d.id for d in service.list(only_available=True)]


def test_delete_and_missing(service):
    service.delete(2)
    with pytest.raises(DishNotFound):
        service.get(2)


# --- integration (HTTP + БД) ---
def test_api_crud(client):
    created = client.post("/dishes", json={"name": "Компот", "category": "drink", "price": 150})
    assert created.status_code == 201
    dish_id = created.json()["id"]
    assert (
        client.put(
            f"/dishes/{dish_id}",
            json={"name": "Компот вишнёвый", "category": "drink", "price": 170},
        ).json()["price"]
        == 170
    )
    assert client.delete(f"/dishes/{dish_id}").status_code == 204
    assert client.get(f"/dishes/{dish_id}").status_code == 404


def test_api_errors_and_health(client):
    invalid = {"name": "", "category": "x", "price": -1}
    assert client.post("/dishes", json=invalid).status_code == 422
    assert client.get("/dishes?ids=a,b").status_code == 400
    assert (
        client.post("/dishes", json={"name": "Борщ", "category": "soup", "price": 1}).status_code
        == 409
    )
    assert client.get("/health").json()["status"] == "healthy"


def test_fault_injection_for_retry_demo(client):
    client.post("/admin/faults", json={"fail_next": 2})
    assert client.get("/dishes").status_code == 503
    assert client.get("/dishes").status_code == 503
    assert client.get("/dishes").status_code == 200


def test_contract_for_order_service(client):
    # Order Service запрашивает GET /dishes?ids=... и читает id, name, price, is_available
    dishes = client.get("/dishes", params={"ids": "3,8"}).json()
    assert {d["id"] for d in dishes} == {3, 8}
    assert all({"id", "name", "price", "is_available"} <= d.keys() for d in dishes)


def test_health_reports_unavailable_database():
    # БД недоступна: без входа в контекст TestClient lifespan не запускается,
    # и /health сам обнаруживает, что соединиться с БД нельзя
    app = create_app("sqlite:////nonexistent-dir/menu.db")
    response = TestClient(app).get("/health")
    assert response.status_code == 503
