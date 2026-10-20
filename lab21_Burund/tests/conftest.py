import os

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.cache import MenuCache
from app.core.config import Settings
from app.database import Database
from app.main import create_app
from app.models import Role
from app.schemas.auth import RegisterIn
from app.services.auth_service import AuthService
from app.services.menu_service import MenuService

TEST_DB = os.getenv("TEST_DATABASE_URL", "sqlite://")
SECRET = "test-secret-key-with-enough-length-1234"
ADMIN = {"email": "admin@test.ru", "password": "admin12345"}
USER = {
    "email": "ivan@test.ru",
    "password": "ivan12345",
    "full_name": "Иван Петров",
    "phone": "+79001112233",
}


@pytest.fixture
def settings():
    return Settings(
        database_url=TEST_DB,
        redis_url=None,
        broker_url=None,
        jwt_secret=SECRET,
        admin_email=ADMIN["email"],
        admin_password=ADMIN["password"],
        log_level="WARNING",
    )


@pytest.fixture
def db():
    database = Database(TEST_DB)
    database.drop_tables()
    database.create_tables()
    yield database
    database.drop_tables()
    database.engine.dispose()


@pytest.fixture
def cache():
    return MenuCache(fakeredis.FakeRedis(decode_responses=True), ttl=60)


@pytest.fixture
def session(db, cache):
    with db.session_factory() as s:
        MenuService(s, cache).seed()
        yield s


@pytest.fixture
def user(session):
    return AuthService(session, SECRET, 60).register(RegisterIn(**USER))


@pytest.fixture
def admin(session):
    data = RegisterIn(
        email=ADMIN["email"], full_name="Админ", phone="+79000000000", password=ADMIN["password"]
    )
    return AuthService(session, SECRET, 60).register(data, role=Role.ADMIN)


@pytest.fixture
def client(settings, db, cache):
    with TestClient(create_app(settings, db, cache)) as test_client:
        yield test_client


def token_for(client, email: str, password: str) -> dict:
    response = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def user_headers(client):
    client.post("/auth/register", json=USER)
    return token_for(client, USER["email"], USER["password"])


@pytest.fixture
def admin_headers(client):
    return token_for(client, ADMIN["email"], ADMIN["password"])
