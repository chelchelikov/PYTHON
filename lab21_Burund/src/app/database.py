from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str) -> None:
        kwargs = {}
        if url.startswith("sqlite"):
            kwargs = {"connect_args": {"check_same_thread": False}}
            if ":memory:" in url or url == "sqlite://":
                kwargs["poolclass"] = StaticPool
        self.engine = create_engine(url, pool_pre_ping=True, **kwargs)
        if url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def _fk_on(connection, _):
                connection.execute("PRAGMA foreign_keys = ON")

        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_tables(self) -> None:
        from app import models  # noqa: F401  регистрация моделей

        Base.metadata.create_all(self.engine)

    def drop_tables(self) -> None:
        Base.metadata.drop_all(self.engine)

    def session(self):
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()
