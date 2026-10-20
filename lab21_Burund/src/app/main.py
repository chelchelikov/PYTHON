"""Итоговый проект. Вариант 5. Ресторан: полный цикл заказа с доставкой.

Запуск: uvicorn app.main:app --app-dir src     Документация: /docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import auth, dishes, orders
from app.cache import MenuCache, create_cache
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import setup_logging
from app.database import Database
from app.repositories import OutboxRepository
from app.services.auth_service import AuthService
from app.services.menu_service import MenuService

log = logging.getLogger("restaurant")


def create_app(
    settings: Settings | None = None, db: Database | None = None, cache: MenuCache | None = None
) -> FastAPI:
    settings = settings or get_settings()
    db = db or Database(settings.database_url)
    cache = cache or create_cache(settings.redis_url, settings.menu_cache_ttl)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.create_tables()
        with db.session_factory() as session:
            AuthService(session, settings.jwt_secret, settings.jwt_expire_minutes).ensure_admin(
                settings.admin_email, settings.admin_password
            )
            if settings.seed_demo_data:
                MenuService(session, cache).seed()
        log.info("%s запущен", settings.app_name)
        yield

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        description="Ресторан с доставкой: меню, заказы, "
        "доставка, роли USER/ADMIN. Авторизация — кнопка Authorize (POST /auth/token).",
    )
    app.state.settings, app.state.db, app.state.cache = settings, db, cache
    setup_logging(app, settings.log_level)
    for router in (auth.router, dishes.router, orders.router):
        app.include_router(router)

    @app.exception_handler(AppError)
    async def app_error(_: Request, error: AppError):
        return JSONResponse(
            {"error": error.code, "message": error.message}, status_code=error.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
            for e in error.errors()
        ]
        return JSONResponse(
            {"error": "VALIDATION_ERROR", "message": "Некорректные данные", "details": details},
            status_code=422,
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_error(_: Request, error: SQLAlchemyError):
        log.exception("Ошибка базы данных")
        return JSONResponse(
            {"error": "DATABASE_ERROR", "message": "Ошибка базы данных"}, status_code=500
        )

    @app.get("/health", tags=["Служебное"], summary="Состояние приложения и зависимостей")
    def health():
        try:
            with db.session_factory() as session:
                session.execute(text("SELECT 1"))
                backlog = OutboxRepository(session).backlog()
            database = "healthy"
        except SQLAlchemyError:
            database, backlog = "unavailable", None
        status = "healthy" if database == "healthy" else "unhealthy"
        body = {
            "status": status,
            "database": database,
            "redis": cache.ping(),
            "outbox_backlog": backlog,
        }
        return JSONResponse(body, status_code=200 if status == "healthy" else 503)

    return app


app = create_app()
