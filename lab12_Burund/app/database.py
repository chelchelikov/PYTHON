import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DEFAULT_URL = "postgresql+psycopg://restaurant:restaurant@localhost:5432/restaurant"


class Base(DeclarativeBase):
    pass


def create_db_engine(url: str | None = None, echo: bool = False) -> Engine:
    return create_engine(url or os.getenv("DATABASE_URL", DEFAULT_URL), echo=echo)


def create_session_factory(engine: Engine) -> sessionmaker:
    # expire_on_commit=False: объекты остаются доступными после закрытия сессии
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine, drop: bool = False) -> None:
    from app.models import entities  # noqa: F401  регистрация моделей в Base.metadata

    if drop:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
