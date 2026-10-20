import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.cache import MenuCache
from app.core.errors import ConflictError, NotFoundError
from app.models import Dish
from app.repositories import DishRepository
from app.schemas.dish import DishIn, DishOut, DishPatch

log = logging.getLogger("restaurant.menu")

DEMO_MENU = [
    ("Цезарь с курицей", "salad", 450, "Романо, курица гриль, пармезан"),
    ("Греческий салат", "salad", 390, "Томаты, огурцы, фета, маслины"),
    ("Борщ", "soup", 350, "Со сметаной и пампушками"),
    ("Том ям", "soup", 520, "Креветки, кокосовое молоко, лемонграсс"),
    ("Стейк рибай", "main", 1890, "Мраморная говядина, соус демиглас"),
    ("Паста карбонара", "main", 590, "Гуанчале, желток, пекорино"),
    ("Лосось на гриле", "main", 1250, "С овощами и лимонным соусом"),
    ("Чизкейк", "dessert", 380, "Нью-йоркский классический"),
    ("Тирамису", "dessert", 420, "Маскарпоне, савоярди, эспрессо"),
    ("Морс клюквенный", "drink", 190, "Домашний, без сахара"),
]


class MenuService:
    def __init__(self, session: Session, cache: MenuCache) -> None:
        self.session = session
        self.dishes = DishRepository(session)
        self.cache = cache
        self.last_cache_hit = False

    def search(self, filters: dict[str, Any], sort: str, limit: int, offset: int) -> dict:
        key = json.dumps(
            {**filters, "sort": sort, "limit": limit, "offset": offset}, sort_keys=True, default=str
        )
        cached = self.cache.get(key)
        self.last_cache_hit = cached is not None
        if cached is not None:
            return cached
        total, items = self.dishes.search(filters, sort, limit, offset)
        result = {
            "total": total,
            "items": [DishOut.model_validate(d).model_dump(mode="json") for d in items],
        }
        self.cache.set(key, result)
        return result

    def get(self, dish_id: int) -> Dish:
        dish = self.dishes.get(dish_id)
        if dish is None:
            raise NotFoundError(f"Блюдо {dish_id} не найдено", "DISH_NOT_FOUND")
        return dish

    def _ensure_unique(self, name: str, dish_id: int | None = None) -> None:
        existing = self.dishes.by_name(name)
        if existing is not None and existing.id != dish_id:
            raise ConflictError(f"Блюдо «{name}» уже есть в меню", "DISH_EXISTS")

    def _save(self, dish: Dish) -> Dish:
        self.session.commit()
        self.cache.invalidate()
        return dish

    def create(self, data: DishIn) -> Dish:
        self._ensure_unique(data.name)
        dish = self.dishes.add(Dish(**data.model_dump()))
        log.info("Добавлено блюдо %s", dish.name)
        return self._save(dish)

    def update(self, dish_id: int, data: DishIn | DishPatch) -> Dish:
        dish = self.get(dish_id)
        changes = data.model_dump(exclude_none=True)
        if "name" in changes:
            self._ensure_unique(changes["name"], dish_id)
        for key, value in changes.items():
            setattr(dish, key, value)
        return self._save(dish)

    def delete(self, dish_id: int) -> None:
        dish = self.get(dish_id)
        if self.dishes.is_ordered(dish_id):
            raise ConflictError(
                "Блюдо есть в заказах — снимите его с продажи (is_available)", "DISH_IN_ORDERS"
            )
        self.dishes.delete(dish)
        self._save(dish)

    def seed(self) -> int:
        if self.dishes.count():
            return 0
        for name, category, price, description in DEMO_MENU:
            self.dishes.add(
                Dish(
                    name=name,
                    category=category,
                    price=price,
                    description=description,
                    portions_available=30,
                )
            )
        self.session.commit()
        return len(DEMO_MENU)
