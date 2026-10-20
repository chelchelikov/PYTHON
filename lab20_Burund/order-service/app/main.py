"""Order Service — заказы (собственная БД orders_db), публикует OrderCreated."""

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import Database
from app.events import EventPublisher, InMemoryPublisher, RabbitMQPublisher
from app.logging_setup import setup_logging
from app.menu_client import MenuClient
from app.resilience import ServiceUnavailable
from app.schemas import OrderIn, OrderOut, OrderStatus, OrderUpdate
from app.service import OrderNotFound, OrderRejected, OrderService

SERVICE_NAME = "order-service"


def create_app(
    database_url: str | None = None,
    menu_client: MenuClient | None = None,
    publisher: EventPublisher | None = None,
) -> FastAPI:
    db = Database(database_url or os.getenv("DATABASE_URL", "sqlite:///./orders.db"))
    menu = menu_client or MenuClient(os.getenv("MENU_SERVICE_URL", "http://localhost:8001"))
    broker_url = os.getenv("BROKER_URL")
    events = publisher or (RabbitMQPublisher(broker_url) if broker_url else InMemoryPublisher())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.create_tables()
        yield
        if isinstance(events, RabbitMQPublisher):
            await events.close()

    app = FastAPI(title="Order Service", lifespan=lifespan)
    app.state.menu = menu
    app.state.publisher = events
    setup_logging(app, SERVICE_NAME)

    def service(session=Depends(db.session)) -> OrderService:
        return OrderService(session, menu, events)

    @app.exception_handler(OrderNotFound)
    async def not_found(_, error):
        return JSONResponse({"detail": str(error)}, status_code=404)

    @app.exception_handler(OrderRejected)
    async def rejected(_, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(ServiceUnavailable)
    async def unavailable(_, error):
        return JSONResponse({"detail": str(error)}, status_code=503)

    @app.get("/health")
    def health():
        try:
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as error:
            raise HTTPException(503, f"database unavailable: {error}") from None
        return {
            "status": "healthy",
            "service": SERVICE_NAME,
            "menu_circuit": menu.breaker.state.value,
        }

    @app.get("/orders", response_model=list[OrderOut])
    def list_orders(status: OrderStatus | None = None, orders: OrderService = Depends(service)):
        return orders.list(status.value if status else None)

    @app.get("/orders/{order_id}", response_model=OrderOut)
    def get_order(order_id: int, orders: OrderService = Depends(service)):
        return orders.get(order_id)

    @app.post("/orders", response_model=OrderOut, status_code=201)
    async def create_order(
        data: OrderIn, request: Request, orders: OrderService = Depends(service)
    ):
        return await orders.create(data, request.state.request_id)

    @app.put("/orders/{order_id}", response_model=OrderOut)
    def update_order(order_id: int, data: OrderUpdate, orders: OrderService = Depends(service)):
        return orders.update(order_id, data)

    @app.delete("/orders/{order_id}", response_model=OrderOut)
    async def cancel_order(order_id: int, orders: OrderService = Depends(service)):
        """Удаление заказа = отмена (история сохраняется), публикуется OrderCancelled."""
        return await orders.cancel(order_id)

    return app


app = create_app()
