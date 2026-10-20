from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.repositories.room import RoomRepository
from app.schemas.room import (RoomCreate, RoomListResponse, RoomPatch, RoomResponse,
                              RoomStatistics, RoomType, SortField, SortOrder)
from app.services.room import RoomService

router = APIRouter(prefix="/rooms", tags=["Номера"])

NOT_FOUND = {404: {"description": "Номер не найден"}}
CONFLICT = {409: {"description": "Номер с таким номером комнаты уже существует"}}


def get_session(request: Request):
    yield from request.app.state.db.session()


def get_service(request: Request, session: Session = Depends(get_session)) -> RoomService:
    return RoomService(RoomRepository(session), request.app.state.cache,
                       request.app.state.settings.cache_ttl)


@router.get("", response_model=RoomListResponse, summary="Список номеров",
            description="Фильтрация по типу, цене, доступности и вместимости, "
                        "сортировка и пагинация (limit/offset).")
def list_rooms(
    room_type: RoomType | None = Query(None, alias="type", description="Тип номера"),
    min_price: float | None = Query(None, ge=0, description="Минимальная цена"),
    max_price: float | None = Query(None, ge=0, description="Максимальная цена"),
    is_available: bool | None = Query(None, description="Только доступные / недоступные"),
    min_capacity: int | None = Query(None, ge=1, description="Минимальная вместимость"),
    floor: int | None = Query(None, ge=0),
    sort: SortField = Query(SortField.number, description="Поле сортировки"),
    order: SortOrder = Query(SortOrder.asc),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: RoomService = Depends(get_service),
):
    filters = {"room_type": room_type.value if room_type else None, "min_price": min_price,
               "max_price": max_price, "is_available": is_available,
               "min_capacity": min_capacity, "floor": floor}
    total, items = service.list_rooms(filters, sort.value, order == SortOrder.desc,
                                      limit, offset)
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/search", response_model=list[RoomResponse], summary="Поиск номеров",
            description="Ищет подстроку в номере комнаты, типе и удобствах.")
def search_rooms(q: str = Query(min_length=1, description="Строка поиска"),
                 limit: int = Query(20, ge=1, le=100),
                 service: RoomService = Depends(get_service)):
    return service.search(q, limit)


@router.get("/statistics", response_model=RoomStatistics, summary="Статистика по номерам")
def statistics(service: RoomService = Depends(get_service)):
    return service.statistics()


@router.get("/{room_id}", response_model=RoomResponse, responses=NOT_FOUND,
            summary="Номер по id (асинхронно, с кэшем Redis)")
async def get_room(room_id: int, response: Response,
                   service: RoomService = Depends(get_service)):
    room = await service.get_room(room_id)
    response.headers["X-Cache"] = "HIT" if service.last_source == "cache" else "MISS"
    return room


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED,
             responses=CONFLICT, summary="Создать номер")
def create_room(data: RoomCreate, response: Response,
                service: RoomService = Depends(get_service)):
    room = service.create(data)
    response.headers["Location"] = f"/rooms/{room.id}"
    return room


@router.put("/{room_id}", response_model=RoomResponse, responses={**NOT_FOUND, **CONFLICT},
            summary="Полностью заменить номер")
async def replace_room(room_id: int, data: RoomCreate,
                       service: RoomService = Depends(get_service)):
    return await service.replace(room_id, data)


@router.patch("/{room_id}", response_model=RoomResponse, responses={**NOT_FOUND, **CONFLICT},
              summary="Частично изменить номер")
async def patch_room(room_id: int, data: RoomPatch,
                     service: RoomService = Depends(get_service)):
    return await service.patch(room_id, data)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND,
               summary="Удалить номер")
async def delete_room(room_id: int, service: RoomService = Depends(get_service)):
    await service.delete(room_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
