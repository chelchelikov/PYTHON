from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Dish


class DishRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(
        self,
        category: str | None = None,
        ids: list[int] | None = None,
        only_available: bool = False,
    ) -> list[Dish]:
        stmt = select(Dish).order_by(Dish.category, Dish.name)
        if category:
            stmt = stmt.where(Dish.category == category)
        if ids is not None:
            stmt = stmt.where(Dish.id.in_(ids))
        if only_available:
            stmt = stmt.where(Dish.is_available.is_(True))
        return list(self.session.scalars(stmt))

    def get(self, dish_id: int) -> Dish | None:
        return self.session.get(Dish, dish_id)

    def get_by_name(self, name: str) -> Dish | None:
        return self.session.scalars(select(Dish).where(Dish.name == name)).first()

    def save(self, dish: Dish) -> Dish:
        self.session.add(dish)
        self.session.commit()
        self.session.refresh(dish)
        return dish

    def delete(self, dish: Dish) -> None:
        self.session.delete(dish)
        self.session.commit()

    def count(self) -> int:
        return len(self.list())
