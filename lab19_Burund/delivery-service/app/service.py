import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Delivery
from app.schemas import DeliveryIn, DeliveryStatus, DeliveryUpdate

log = logging.getLogger("delivery-service")

COURIERS = ["Алексей", "Мария", "Тимур", "Ольга"]
BASE_ETA = 30
ETA_PER_ITEM = 5


class DeliveryNotFound(Exception):
    pass


class DeliveryConflict(Exception):
    pass


class DeliveryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _next_courier(self) -> str:
        # Курьер с наименьшим числом активных доставок
        load = dict(self.session.execute(
            select(Delivery.courier, func.count(Delivery.id))
            .where(Delivery.status.in_([DeliveryStatus.assigned.value,
                                        DeliveryStatus.on_the_way.value]))
            .group_by(Delivery.courier)).all())
        return min(COURIERS, key=lambda name: (load.get(name, 0), COURIERS.index(name)))

    def list(self, status: str | None = None) -> list[Delivery]:
        stmt = select(Delivery).order_by(Delivery.id.desc())
        if status:
            stmt = stmt.where(Delivery.status == status)
        return list(self.session.scalars(stmt))

    def get(self, delivery_id: int) -> Delivery:
        delivery = self.session.get(Delivery, delivery_id)
        if delivery is None:
            raise DeliveryNotFound(f"Доставка {delivery_id} не найдена")
        return delivery

    def by_order(self, order_id: int) -> Delivery:
        delivery = self.session.scalars(select(Delivery).where(Delivery.order_id == order_id)).first()
        if delivery is None:
            raise DeliveryNotFound(f"Доставка для заказа {order_id} не найдена")
        return delivery

    def create(self, data: DeliveryIn, items_count: int = 1) -> Delivery:
        if self.session.scalars(select(Delivery).where(Delivery.order_id == data.order_id)).first():
            raise DeliveryConflict(f"Доставка для заказа {data.order_id} уже существует")
        delivery = Delivery(**data.model_dump(), courier=self._next_courier(),
                            status=DeliveryStatus.assigned.value,
                            eta_minutes=BASE_ETA + ETA_PER_ITEM * items_count)
        self.session.add(delivery)
        self.session.commit()
        self.session.refresh(delivery)
        log.info("Доставка %s для заказа %s назначена курьеру %s", delivery.id,
                 delivery.order_id, delivery.courier)
        return delivery

    def update(self, delivery_id: int, data: DeliveryUpdate) -> Delivery:
        delivery = self.get(delivery_id)
        if delivery.status in (DeliveryStatus.delivered.value, DeliveryStatus.cancelled.value):
            raise DeliveryConflict(f"Доставка в статусе «{delivery.status}» уже завершена")
        for key, value in data.model_dump(mode="json").items():
            setattr(delivery, key, value)
        self.session.commit()
        return delivery

    def delete(self, delivery_id: int) -> None:
        self.session.delete(self.get(delivery_id))
        self.session.commit()

    # --- обработка событий из брокера ---
    def handle_event(self, routing_key: str, payload: dict) -> Delivery | None:
        """Идемпотентная обработка: повторная доставка того же события ничего не ломает."""
        if routing_key == "order.created":
            try:
                return self.create(DeliveryIn(
                    order_id=payload["order_id"], customer_name=payload["customer_name"],
                    phone=payload["phone"], address=payload["address"],
                    order_total=payload["total"]),
                    items_count=sum(i["quantity"] for i in payload.get("items", [])) or 1)
            except DeliveryConflict:
                log.info("OrderCreated для заказа %s уже обработано", payload["order_id"])
                return self.by_order(payload["order_id"])
        if routing_key == "order.cancelled":
            try:
                delivery = self.by_order(payload["order_id"])
            except DeliveryNotFound:
                return None
            if delivery.status != DeliveryStatus.delivered.value:
                delivery.status = DeliveryStatus.cancelled.value
                self.session.commit()
                log.info("Доставка %s отменена вместе с заказом", delivery.id)
            return delivery
        log.warning("Неизвестное событие %s", routing_key)
        return None
