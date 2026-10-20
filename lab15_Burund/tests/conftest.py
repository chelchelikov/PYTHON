import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture
def app():
    application = create_app(TestConfig)
    database = application.extensions["database"]
    database.drop_all()
    database.create_all()
    with database.session_factory() as session:
        seed(session)
    yield application
    database.drop_all()
    database.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def session(app):
    with app.app_context():
        from app.database import get_session
        yield get_session()
