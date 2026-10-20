import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import EventPublisher
from app.menu_client import MenuClient
from app.models import Order, OrderItem
from app.schemas import OrderIn, OrderStatus, OrderUpdate

log = logging.getLogger("order-service")


class OrderNotFound(Exception):
    pass


class OrderRejected(Exception):
    """Заказ нельзя создать или изменить (блюдо недоступно, недопустимый статус)."""


class OrderService:
    def __init__(self, session: Session, menu: MenuClient, publisher: EventPublisher) -> None:
        self.session = session
        self.menu = menu
        self.publisher = publisher

    def list(self, status: str | None = None) -> list[Order]:
        stmt = select(Order).order_by(Order.id.desc())
        if status:
            stmt = stmt.where(Order.status == status)
        return list(self.session.scalars(stmt))

    def get(self, order_id: int) -> Order:
        order = self.session.get(Order, order_id)
        if order is None:
            raise OrderNotFound(f"Заказ {order_id} не найден")
        return order

    async def create(self, data: OrderIn, request_id: str | None = None) -> Order:
        quantities: dict[int, int] = {}
        for item in data.items:
            quantities[item.dish_id] = quantities.get(item.dish_id, 0) + item.quantity
        # Межсервисный вызов: Order Service -> Menu Service (Retry + Circuit Breaker)
        dishes = {d["id"]: d for d in await self.menu.get_dishes(list(quantities), request_id)}
        missing = sorted(set(quantities) - set(dishes))
        if missing:
            raise OrderRejected(f"Блюда не найдены в меню: {missing}")
        unavailable = [d["name"] for d in dishes.values() if not d["is_available"]]
        if unavailable:
            raise OrderRejected(f"Сейчас недоступны: {', '.join(unavailable)}")

        order = Order(customer_name=data.customer_name, phone=data.phone, address=data.address,
                      total=0)
        for dish_id, quantity in quantities.items():
            dish = dishes[dish_id]
            order.items.append(OrderItem(dish_id=dish_id, name=dish["name"], price=dish["price"],
                                         quantity=quantity))
        order.total = round(sum(i.price * i.quantity for i in order.items), 2)
        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)
        log.info("Создан заказ %s на %.2f", order.id, order.total)
        await self.publisher.publish("order.created", self.event_payload(order))
        return order

    @staticmethod
    def event_payload(order: Order) -> dict:
        return {"event": "OrderCreated", "order_id": order.id,
                "customer_name": order.customer_name, "phone": order.phone,
                "address": order.address, "total": order.total,
                "items": [{"dish_id": i.dish_id, "name": i.name, "quantity": i.quantity}
                          for i in order.items]}

    def update(self, order_id: int, data: OrderUpdate) -> Order:
        order = self.get(order_id)
        if order.status in (OrderStatus.cancelled, OrderStatus.delivered):
            raise OrderRejected(f"Заказ в статусе «{order.status}» изменить нельзя")
        for key, value in data.model_dump(mode="json").items():
            setattr(order, key, value)
        self.session.commit()
        return order

    async def cancel(self, order_id: int) -> Order:
        order = self.get(order_id)
        if order.status in (OrderStatus.cancelled, OrderStatus.delivered):
            raise OrderRejected(f"Заказ в статусе «{order.status}» отменить нельзя")
        order.status = OrderStatus.cancelled.value
        self.session.commit()
        await self.publisher.publish("order.cancelled",
                                     {"event": "OrderCancelled", "order_id": order.id})
        return order
