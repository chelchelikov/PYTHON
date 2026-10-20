import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import event  # noqa: E402

from app.database import create_db_engine, create_session_factory, init_db  # noqa: E402
from app.seed import seed  # noqa: E402

# По умолчанию тесты работают на SQLite в памяти; для PostgreSQL:
#   TEST_DATABASE_URL=postgresql+psycopg://restaurant:restaurant@localhost/restaurant_test pytest
TEST_URL = os.getenv("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")


@pytest.fixture
def session_factory():
    engine = create_db_engine(TEST_URL)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys = ON")
    init_db(engine, drop=True)
    factory = create_session_factory(engine)
    seed(factory)
    yield factory
    engine.dispose()
