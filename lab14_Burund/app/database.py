from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def create_db_engine(url: str) -> Engine:
    if url.startswith("sqlite") and ":memory:" in url:
        # Одна общая in-memory БД для всех соединений (используется в тестах)
        return create_engine(url, connect_args={"check_same_thread": False},
                             poolclass=StaticPool)
    return create_engine(url, pool_pre_ping=True)


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_db_engine(url)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_tables(self) -> None:
        from app.models import room  # noqa: F401

        Base.metadata.create_all(self.engine)

    def drop_tables(self) -> None:
        Base.metadata.drop_all(self.engine)

    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()
