"""Бизнес-логика заказов.

Правила:
1. Нельзя заказать блюдо, которого нет, которое снято с продажи или порций не хватает;
   порции списываются при заказе и возвращаются при отмене.
2. Минимальная сумма заказа — MIN_ORDER_TOTAL; доставка бесплатна от FREE_DELIVERY_FROM.
3. Статус меняется только по разрешённым переходам; отменить можно лишь до приготовления.
4. Пользователь видит и отменяет только свои заказы, администратор — любые.
"""

import logging

from sqlalchemy.orm import Session

from app.cache import MenuCache
from app.core.errors import BusinessRuleError, ForbiddenError, NotFoundError
from app.models import Delivery, DeliveryStatus, Order, OrderItem, OrderStatus, Role, User
from app.repositories import DishRepository, OrderRepository, OutboxRepository
from app.schemas.order import OrderIn

log = logging.getLogger("restaurant.orders")

MIN_ORDER_TOTAL = 500.0
FREE_DELIVERY_FROM = 2000.0
DELIVERY_FEE = 199.0

TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.COOKING, OrderStatus.CANCELLED},
    OrderStatus.COOKING: {OrderStatus.READY, OrderStatus.CANCELLED},
    OrderStatus.READY: {OrderStatus.DELIVERING},
    OrderStatus.DELIVERING: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}
CANCELLABLE = {OrderStatus.CREATED, OrderStatus.COOKING}


def delivery_fee(items_total: float) -> float:
    return 0.0 if items_total >= FREE_DELIVERY_FROM else DELIVERY_FEE


class OrderService:
    def __init__(self, session: Session, cache: MenuCache) -> None:
        self.session = session
        self.orders = OrderRepository(session)
        self.dishes = DishRepository(session)
        self.outbox = OutboxRepository(session)
        self.cache = cache

    def create(self, user: User, data: OrderIn) -> Order:
        quantities = {item.dish_id: item.quantity for item in data.items}
        dishes = self.dishes.lock_many(list(quantities))
        order = Order(
            user_id=user.id,
            address=data.address,
            comment=data.comment,
            items_total=0,
            delivery_fee=0,
            total=0,
        )
        for dish_id, quantity in quantities.items():
            dish = dishes.get(dish_id)
            if dish is None:
                raise NotFoundError(f"Блюдо {dish_id} не найдено", "DISH_NOT_FOUND")
            if not dish.is_available:
                raise BusinessRuleError(f"Блюдо «{dish.name}» снято с продажи", "DISH_UNAVAILABLE")
            if dish.portions_available < quantity:
                raise BusinessRuleError(
                    f"«{dish.name}»: доступно {dish.portions_available} порц., "
                    f"запрошено {quantity}",
                    "NOT_ENOUGH_PORTIONS",
                )
            dish.portions_available -= quantity
            order.items.append(OrderItem(dish=dish, quantity=quantity, price=dish.price))
        items_total = round(sum(i.price * i.quantity for i in order.items), 2)
        if items_total < MIN_ORDER_TOTAL:
            raise BusinessRuleError(
                f"Минимальная сумма заказа — {MIN_ORDER_TOTAL:.0f} ₽", "ORDER_TOO_SMALL"
            )
        order.items_total = items_total
        order.delivery_fee = delivery_fee(items_total)
        order.total = items_total + order.delivery_fee
        order.delivery = Delivery(address=data.address, status=DeliveryStatus.PENDING)
        self.orders.add(order)
        # Событие пишется в outbox в той же транзакции: заказ и событие сохраняются вместе
        self.outbox.add(
            "order.created",
            {
                "order_id": order.id,
                "items": len(order.items),
                "address": order.address,
                "total": order.total,
            },
        )
        self.session.commit()
        self.cache.invalidate()  # изменились остатки порций в меню
        log.info("Заказ %s создан пользователем %s на %.2f ₽", order.id, user.id, order.total)
        return order

    def get(self, user: User, order_id: int) -> Order:
        order = self.orders.get(order_id)
        if order is None:
            raise NotFoundError(f"Заказ {order_id} не найден", "ORDER_NOT_FOUND")
        if user.role != Role.ADMIN and order.user_id != user.id:
            raise ForbiddenError("Это чужой заказ", "NOT_YOUR_ORDER")
        return order

    def find(
        self, user: User, status: OrderStatus | None, newest_first: bool, limit: int, offset: int
    ) -> list[Order]:
        owner = None if user.role == Role.ADMIN else user.id
        return self.orders.find(owner, status, newest_first, limit, offset)

    def change_status(self, order_id: int, new_status: OrderStatus, admin: User) -> Order:
        order = self.get(admin, order_id)
        if new_status == OrderStatus.CANCELLED:
            return self.cancel(admin, order_id)
        if new_status not in TRANSITIONS[order.status]:
            raise BusinessRuleError(
                f"Нельзя перейти из «{order.status}» в «{new_status}»", "INVALID_TRANSITION"
            )
        order.status = new_status
        if new_status == OrderStatus.DELIVERING and order.delivery:
            order.delivery.status = DeliveryStatus.ON_THE_WAY
        if new_status == OrderStatus.DELIVERED and order.delivery:
            order.delivery.status = DeliveryStatus.DELIVERED
        self.session.commit()
        log.info("Заказ %s: статус %s", order_id, new_status)
        return order

    def cancel(self, user: User, order_id: int) -> Order:
        order = self.get(user, order_id)
        if order.status not in CANCELLABLE:
            raise BusinessRuleError(
                f"Заказ в статусе «{order.status}» отменить нельзя", "CANNOT_CANCEL"
            )
        for item in order.items:
            item.dish.portions_available += item.quantity
        order.status = OrderStatus.CANCELLED
        if order.delivery:
            order.delivery.status = DeliveryStatus.CANCELLED
        self.outbox.add("order.cancelled", {"order_id": order.id})
        self.session.commit()
        self.cache.invalidate()
        log.info("Заказ %s отменён", order_id)
        return order

    def delete(self, admin: User, order_id: int) -> None:
        order = self.get(admin, order_id)
        if order.status not in (OrderStatus.CANCELLED, OrderStatus.DELIVERED):
            raise BusinessRuleError(
                "Удалить можно только завершённый или отменённый заказ", "ORDER_ACTIVE"
            )
        self.orders.delete(order)
        self.session.commit()

    def statistics(self) -> dict:
        return self.orders.statistics()
