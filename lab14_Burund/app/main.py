"""Лабораторная работа №14. Вариант 5. Отель — REST API на FastAPI.

Запуск:  uvicorn app.main:app --reload    Swagger UI: http://127.0.0.1:8000/docs
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.cache import Cache, create_cache
from app.config import Settings, get_settings
from app.database import Database
from app.routers import rooms
from app.services.room import RoomConflict, RoomNotFound

log = logging.getLogger("hotel.api")


def create_app(settings: Settings | None = None, db: Database | None = None,
               cache: Cache | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.db.create_tables()
        log.info("Приложение запущено (%s)", settings.app_env)
        yield

    app = FastAPI(title="Отель — API номеров",
                  description="Лабораторная работа №14, вариант 5. CRUD, поиск, фильтрация, "
                              "сортировка, пагинация и статистика по номерам отеля.",
                  version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db or Database(settings.database_url)
    app.state.cache = cache or create_cache(settings.redis_url)
    app.include_router(rooms.router)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        log.info("%s %s -> %s (%.1f мс)", request.method, request.url.path,
                 response.status_code, (time.perf_counter() - start) * 1000)
        return response

    @app.exception_handler(RoomNotFound)
    async def not_found(_: Request, error: RoomNotFound):
        return JSONResponse({"detail": str(error)}, status_code=status.HTTP_404_NOT_FOUND)

    @app.exception_handler(RoomConflict)
    async def conflict(_: Request, error: RoomConflict):
        return JSONResponse({"detail": str(error)}, status_code=status.HTTP_409_CONFLICT)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError):
        errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
                  for e in error.errors()]
        return JSONResponse({"detail": "Ошибка валидации", "errors": errors},
                            status_code=422)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_: Request, error: SQLAlchemyError):
        log.exception("Ошибка базы данных")
        return JSONResponse({"detail": "Ошибка базы данных"},
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @app.get("/health", tags=["Служебное"], summary="Проверка работоспособности")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
