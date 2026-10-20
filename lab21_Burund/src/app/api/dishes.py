from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import admin_user, get_cache, get_session
from app.models import DishCategory
from app.schemas.dish import DishIn, DishOut, DishPage, DishPatch, DishSort
from app.services.menu_service import MenuService

router = APIRouter(prefix="/dishes", tags=["Меню"])
ADMIN = {401: {"description": "Нет токена"}, 403: {"description": "Только администратор"}}


def menu(session: Session = Depends(get_session), cache=Depends(get_cache)) -> MenuService:
    return MenuService(session, cache)


@router.get(
    "",
    response_model=DishPage,
    summary="Меню: поиск, фильтры, сортировка",
    description="Публичный endpoint. Ответ кэшируется в Redis (заголовок X-Cache).",
)
def list_dishes(
    response: Response,
    q: str | None = Query(None, max_length=50, description="Поиск по названию"),
    category: DishCategory | None = None,
    max_price: float | None = Query(None, gt=0),
    available_only: bool = Query(False, description="Только доступные к заказу"),
    sort: DishSort = DishSort.name,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: MenuService = Depends(menu),
):
    filters = {
        "q": q,
        "category": category,
        "max_price": max_price,
        "available_only": available_only,
    }
    result = service.search(filters, sort.value, limit, offset)
    response.headers["X-Cache"] = "HIT" if service.last_cache_hit else "MISS"
    return result


@router.get(
    "/{dish_id}",
    response_model=DishOut,
    summary="Блюдо",
    responses={404: {"description": "Не найдено"}},
)
def get_dish(dish_id: int, service: MenuService = Depends(menu)):
    return service.get(dish_id)


@router.post(
    "",
    response_model=DishOut,
    status_code=201,
    summary="Добавить блюдо",
    responses={**ADMIN, 409: {"description": "Название занято"}},
    dependencies=[Depends(admin_user)],
)
def create_dish(data: DishIn, service: MenuService = Depends(menu)):
    return service.create(data)


@router.put(
    "/{dish_id}",
    response_model=DishOut,
    summary="Заменить блюдо",
    responses=ADMIN,
    dependencies=[Depends(admin_user)],
)
def replace_dish(dish_id: int, data: DishIn, service: MenuService = Depends(menu)):
    return service.update(dish_id, data)


@router.patch(
    "/{dish_id}",
    response_model=DishOut,
    summary="Изменить блюдо",
    responses=ADMIN,
    dependencies=[Depends(admin_user)],
)
def patch_dish(dish_id: int, data: DishPatch, service: MenuService = Depends(menu)):
    return service.update(dish_id, data)


@router.delete(
    "/{dish_id}",
    status_code=204,
    summary="Удалить блюдо",
    responses=ADMIN,
    dependencies=[Depends(admin_user)],
)
def delete_dish(dish_id: int, service: MenuService = Depends(menu)):
    service.delete(dish_id)
    return Response(status_code=204)
