"""Delivery Service — доставки (собственная БД delivery_db), слушает OrderCreated."""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.consumer import consume
from app.database import Database
from app.logging_setup import setup_logging
from app.schemas import DeliveryIn, DeliveryOut, DeliveryStatus, DeliveryUpdate
from app.service import DeliveryConflict, DeliveryNotFound, DeliveryService

SERVICE_NAME = "delivery-service"


def create_app(database_url: str | None = None, broker_url: str | None = None) -> FastAPI:
    db = Database(database_url or os.getenv("DATABASE_URL", "sqlite:///./delivery.db"))
    broker = broker_url if broker_url is not None else os.getenv("BROKER_URL")

    def handle_event(routing_key: str, payload: dict) -> None:
        with db.session_factory() as session:
            DeliveryService(session).handle_event(routing_key, payload)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.create_tables()
        stop = asyncio.Event()
        task = asyncio.create_task(consume(broker, handle_event, stop)) if broker else None
        yield
        stop.set()
        if task:
            task.cancel()

    app = FastAPI(title="Delivery Service", lifespan=lifespan)
    app.state.handle_event = handle_event
    setup_logging(app, SERVICE_NAME)

    def service(session=Depends(db.session)) -> DeliveryService:
        return DeliveryService(session)

    @app.exception_handler(DeliveryNotFound)
    async def not_found(_, error):
        return JSONResponse({"detail": str(error)}, status_code=404)

    @app.exception_handler(DeliveryConflict)
    async def conflict(_, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.get("/health")
    def health():
        try:
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as error:
            raise HTTPException(503, f"database unavailable: {error}") from None
        return {"status": "healthy", "service": SERVICE_NAME, "broker": bool(broker)}

    @app.get("/deliveries", response_model=list[DeliveryOut])
    def list_deliveries(
        status: DeliveryStatus | None = None, deliveries: DeliveryService = Depends(service)
    ):
        return deliveries.list(status.value if status else None)

    @app.get("/deliveries/by-order/{order_id}", response_model=DeliveryOut)
    def by_order(order_id: int, deliveries: DeliveryService = Depends(service)):
        return deliveries.by_order(order_id)

    @app.get("/deliveries/{delivery_id}", response_model=DeliveryOut)
    def get_delivery(delivery_id: int, deliveries: DeliveryService = Depends(service)):
        return deliveries.get(delivery_id)

    @app.post("/deliveries", response_model=DeliveryOut, status_code=201)
    def create_delivery(data: DeliveryIn, deliveries: DeliveryService = Depends(service)):
        return deliveries.create(data)

    @app.put("/deliveries/{delivery_id}", response_model=DeliveryOut)
    def update_delivery(
        delivery_id: int, data: DeliveryUpdate, deliveries: DeliveryService = Depends(service)
    ):
        return deliveries.update(delivery_id, data)

    @app.delete("/deliveries/{delivery_id}", status_code=204)
    def delete_delivery(delivery_id: int, deliveries: DeliveryService = Depends(service)):
        deliveries.delete(delivery_id)
        return Response(status_code=204)

    return app


app = create_app()
