from app.models import Dish
from app.repository import DishRepository
from app.schemas import DishIn, DishPatch

DEMO_MENU = [
    ("Цезарь с курицей", "salad", 450), ("Греческий салат", "salad", 390),
    ("Борщ", "soup", 350), ("Том ям", "soup", 520),
    ("Стейк рибай", "main", 1890), ("Паста карбонара", "main", 590),
    ("Лосось на гриле", "main", 1250), ("Чизкейк", "dessert", 380),
    ("Тирамису", "dessert", 420), ("Морс клюквенный", "drink", 190),
]


class DishNotFound(Exception):
    pass


class DishConflict(Exception):
    pass


class MenuService:
    def __init__(self, repository: DishRepository) -> None:
        self.repository = repository

    def list(self, category: str | None = None, ids: list[int] | None = None,
             only_available: bool = False) -> list[Dish]:
        return self.repository.list(category, ids, only_available)

    def get(self, dish_id: int) -> Dish:
        dish = self.repository.get(dish_id)
        if dish is None:
            raise DishNotFound(f"Блюдо {dish_id} не найдено")
        return dish

    def _ensure_unique(self, name: str, dish_id: int | None = None) -> None:
        existing = self.repository.get_by_name(name)
        if existing is not None and existing.id != dish_id:
            raise DishConflict(f"Блюдо «{name}» уже есть в меню")

    def create(self, data: DishIn) -> Dish:
        self._ensure_unique(data.name)
        return self.repository.save(Dish(**data.model_dump(mode="json")))

    def replace(self, dish_id: int, data: DishIn) -> Dish:
        dish = self.get(dish_id)
        self._ensure_unique(data.name, dish_id)
        for key, value in data.model_dump(mode="json").items():
            setattr(dish, key, value)
        return self.repository.save(dish)

    def patch(self, dish_id: int, data: DishPatch) -> Dish:
        dish = self.get(dish_id)
        changes = data.model_dump(mode="json", exclude_none=True)
        if "name" in changes:
            self._ensure_unique(changes["name"], dish_id)
        for key, value in changes.items():
            setattr(dish, key, value)
        return self.repository.save(dish)

    def delete(self, dish_id: int) -> None:
        self.repository.delete(self.get(dish_id))

    def seed(self) -> int:
        if self.repository.count():
            return 0
        for name, category, price in DEMO_MENU:
            self.repository.save(Dish(name=name, category=category, price=price))
        return len(DEMO_MENU)
