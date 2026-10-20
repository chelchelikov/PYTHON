from flask import Flask, g
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Database:
    """Engine и фабрика сессий; одна сессия на HTTP-запрос (хранится в flask.g)."""

    def __init__(self, url: str) -> None:
        kwargs = {}
        if url.startswith("sqlite") and ":memory:" in url:
            kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
        self.engine = create_engine(url, **kwargs)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def init_app(self, app: Flask) -> None:
        app.extensions["database"] = self
        app.teardown_appcontext(self._close_session)

    def create_all(self) -> None:
        from app.models import models  # noqa: F401

        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        Base.metadata.drop_all(self.engine)

    @staticmethod
    def _close_session(_exception=None) -> None:
        session = g.pop("db_session", None)
        if session is not None:
            session.close()


def get_session() -> Session:
    from flask import current_app

    if "db_session" not in g:
        g.db_session = current_app.extensions["database"].session_factory()
    return g.db_session
