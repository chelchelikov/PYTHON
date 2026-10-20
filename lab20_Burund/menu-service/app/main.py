"""Menu Service — меню ресторана (собственная БД menu_db)."""

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import Database
from app.logging_setup import setup_logging
from app.repository import DishRepository
from app.schemas import Category, DishIn, DishOut, DishPatch
from app.service import DishConflict, DishNotFound, MenuService

SERVICE_NAME = "menu-service"


class FaultInjection(BaseModel):
    fail_next: int = Field(ge=0, le=100, description="сколько следующих запросов вернут 503")


def create_app(database_url: str | None = None) -> FastAPI:
    db = Database(database_url or os.getenv("DATABASE_URL", "sqlite:///./menu.db"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.create_tables()
        with db.session_factory() as session:
            MenuService(DishRepository(session)).seed()
        yield

    app = FastAPI(title="Menu Service", lifespan=lifespan)
    app.state.faults = 0
    log = setup_logging(app, SERVICE_NAME)

    @app.middleware("http")
    async def inject_faults(request: Request, call_next):
        # Имитация временного сбоя для демонстрации Retry: следующие N запросов к /dishes → 503
        if request.url.path.startswith("/dishes") and app.state.faults > 0:
            app.state.faults -= 1
            log.warning("Имитация сбоя: осталось %s", app.state.faults)
            return JSONResponse({"detail": "Временная ошибка (имитация)"}, status_code=503)
        return await call_next(request)

    def service(session=Depends(db.session)) -> MenuService:
        return MenuService(DishRepository(session))

    @app.exception_handler(DishNotFound)
    async def not_found(_, error):
        return JSONResponse({"detail": str(error)}, status_code=404)

    @app.exception_handler(DishConflict)
    async def conflict(_, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.get("/health")
    def health():
        try:
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as error:  # БД недоступна
            raise HTTPException(503, f"database unavailable: {error}") from None
        return {"status": "healthy", "service": SERVICE_NAME}

    @app.get("/dishes", response_model=list[DishOut])
    def list_dishes(
        category: Category | None = None,
        ids: str | None = Query(None, description="id через запятую: 1,2,3"),
        available: bool = False,
        menu: MenuService = Depends(service),
    ):
        id_list = None
        if ids:
            try:
                id_list = [int(x) for x in ids.split(",") if x.strip()]
            except ValueError:
                raise HTTPException(400, "ids: целые числа через запятую") from None
        return menu.list(category.value if category else None, id_list, available)

    @app.get("/dishes/{dish_id}", response_model=DishOut)
    def get_dish(dish_id: int, menu: MenuService = Depends(service)):
        return menu.get(dish_id)

    @app.post("/dishes", response_model=DishOut, status_code=201)
    def create_dish(data: DishIn, menu: MenuService = Depends(service)):
        return menu.create(data)

    @app.put("/dishes/{dish_id}", response_model=DishOut)
    def replace_dish(dish_id: int, data: DishIn, menu: MenuService = Depends(service)):
        return menu.replace(dish_id, data)

    @app.patch("/dishes/{dish_id}", response_model=DishOut)
    def patch_dish(dish_id: int, data: DishPatch, menu: MenuService = Depends(service)):
        return menu.patch(dish_id, data)

    @app.delete("/dishes/{dish_id}", status_code=204)
    def delete_dish(dish_id: int, menu: MenuService = Depends(service)):
        menu.delete(dish_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/admin/faults")
    def set_faults(data: FaultInjection):
        app.state.faults = data.fail_next
        return {"fail_next": app.state.faults}

    return app


app = create_app()
