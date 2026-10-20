from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import admin_user, current_user, get_cache, get_session
from app.models import DeliveryStatus, OrderStatus, User
from app.schemas.order import DeliveryOut, DeliveryPatch, OrderIn, OrderOut, StatusIn
from app.services.delivery_service import DeliveryService
from app.services.order_service import OrderService

router = APIRouter(tags=["Заказы и доставка"])
AUTH = {
    401: {"description": "Нет токена"},
    403: {"description": "Нет прав"},
    404: {"description": "Не найдено"},
}


def orders(session: Session = Depends(get_session), cache=Depends(get_cache)) -> OrderService:
    return OrderService(session, cache)


def deliveries(session: Session = Depends(get_session)) -> DeliveryService:
    return DeliveryService(session)


@router.post(
    "/orders",
    response_model=OrderOut,
    status_code=201,
    summary="Оформить заказ",
    description="Проверяет блюда и остатки, списывает порции, создаёт доставку и "
    "событие order.created (outbox).",
    responses={**AUTH, 422: {"description": "Нарушено бизнес-правило"}},
)
def create_order(
    data: OrderIn, user: User = Depends(current_user), service: OrderService = Depends(orders)
):
    return OrderOut.from_order(service.create(user, data))


@router.get(
    "/orders",
    response_model=list[OrderOut],
    summary="Заказы",
    description="Пользователь видит свои заказы, администратор — все.",
)
def list_orders(
    status: OrderStatus | None = None,
    sort: str = Query("newest", pattern="^(newest|oldest)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(current_user),
    service: OrderService = Depends(orders),
):
    return [
        OrderOut.from_order(o) for o in service.find(user, status, sort == "newest", limit, offset)
    ]


@router.get("/orders/{order_id}", response_model=OrderOut, summary="Заказ", responses=AUTH)
def get_order(
    order_id: int, user: User = Depends(current_user), service: OrderService = Depends(orders)
):
    return OrderOut.from_order(service.get(user, order_id))


@router.post(
    "/orders/{order_id}/cancel", response_model=OrderOut, summary="Отменить заказ", responses=AUTH
)
def cancel_order(
    order_id: int, user: User = Depends(current_user), service: OrderService = Depends(orders)
):
    return OrderOut.from_order(service.cancel(user, order_id))


@router.patch(
    "/orders/{order_id}/status",
    response_model=OrderOut,
    summary="Сменить статус (администратор)",
    responses=AUTH,
)
def change_status(
    order_id: int,
    data: StatusIn,
    admin: User = Depends(admin_user),
    service: OrderService = Depends(orders),
):
    return OrderOut.from_order(service.change_status(order_id, data.status, admin))


@router.delete(
    "/orders/{order_id}", status_code=204, summary="Удалить заказ (администратор)", responses=AUTH
)
def delete_order(
    order_id: int, admin: User = Depends(admin_user), service: OrderService = Depends(orders)
):
    service.delete(admin, order_id)
    return Response(status_code=204)


@router.get(
    "/deliveries",
    response_model=list[DeliveryOut],
    summary="Доставки (администратор)",
    dependencies=[Depends(admin_user)],
)
def list_deliveries(
    status: DeliveryStatus | None = None, service: DeliveryService = Depends(deliveries)
):
    return service.find(status)


@router.patch(
    "/deliveries/{delivery_id}",
    response_model=DeliveryOut,
    summary="Обновить доставку (администратор)",
    responses=AUTH,
    dependencies=[Depends(admin_user)],
)
def update_delivery(
    delivery_id: int, data: DeliveryPatch, service: DeliveryService = Depends(deliveries)
):
    return service.update(delivery_id, data)


@router.get("/stats", summary="Статистика (администратор)", dependencies=[Depends(admin_user)])
def statistics(service: OrderService = Depends(orders)):
    return service.statistics()
