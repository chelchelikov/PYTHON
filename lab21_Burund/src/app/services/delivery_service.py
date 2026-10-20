"""Доставка: назначение курьера по событию order.created и ручное управление."""

import logging

from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, NotFoundError
from app.models import Delivery, DeliveryStatus, OrderStatus
from app.repositories import DeliveryRepository
from app.schemas.order import DeliveryPatch

log = logging.getLogger("restaurant.delivery")

COURIERS = ["Алексей", "Мария", "Тимур", "Ольга"]
BASE_ETA = 30
ETA_PER_ITEM = 5
FINISHED = {DeliveryStatus.DELIVERED, DeliveryStatus.CANCELLED}


class DeliveryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.deliveries = DeliveryRepository(session)

    def get(self, delivery_id: int) -> Delivery:
        delivery = self.deliveries.get(delivery_id)
        if delivery is None:
            raise NotFoundError(f"Доставка {delivery_id} не найдена", "DELIVERY_NOT_FOUND")
        return delivery

    def find(self, status: DeliveryStatus | None) -> list[Delivery]:
        return self.deliveries.find(status)

    def next_courier(self) -> str:
        load = self.deliveries.courier_load()
        return min(COURIERS, key=lambda name: (load.get(name, 0), COURIERS.index(name)))

    def assign(self, order_id: int, items: int) -> Delivery | None:
        """Обработчик события order.created (идемпотентный)."""
        delivery = self.deliveries.by_order(order_id)
        if delivery is None or delivery.status != DeliveryStatus.PENDING:
            return delivery  # заказ удалён, отменён или уже обработан
        delivery.courier = self.next_courier()
        delivery.eta_minutes = BASE_ETA + ETA_PER_ITEM * max(items, 1)
        delivery.status = DeliveryStatus.ASSIGNED
        self.session.commit()
        log.info("Заказ %s: курьер %s, ~%s мин", order_id, delivery.courier, delivery.eta_minutes)
        return delivery

    def update(self, delivery_id: int, data: DeliveryPatch) -> Delivery:
        delivery = self.get(delivery_id)
        if delivery.status in FINISHED:
            raise BusinessRuleError("Доставка уже завершена", "DELIVERY_FINISHED")
        if data.status == DeliveryStatus.CANCELLED:
            raise BusinessRuleError("Отмена доставки — через отмену заказа", "USE_ORDER_CANCEL")
        changes = data.model_dump(exclude_none=True)
        for key, value in changes.items():
            setattr(delivery, key, value)
        # Синхронизация статуса заказа со статусом доставки
        if delivery.status == DeliveryStatus.ON_THE_WAY:
            delivery.order.status = OrderStatus.DELIVERING
        if delivery.status == DeliveryStatus.DELIVERED:
            delivery.order.status = OrderStatus.DELIVERED
        self.session.commit()
        return delivery

    def handle_event(self, event_type: str, payload: dict) -> None:
        if event_type == "order.created":
            self.assign(payload["order_id"], payload.get("items", 1))
        elif event_type == "order.cancelled":
            log.info(
                "Заказ %s отменён — доставка уже отменена в той же транзакции", payload["order_id"]
            )
        else:
            log.warning("Неизвестное событие %s", event_type)
