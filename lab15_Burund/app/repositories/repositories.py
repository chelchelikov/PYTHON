from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Category, Dish, Order, OrderItem, OrderStatus

DISH_SORTS = {
    "name": Dish.name.asc(),
    "price": Dish.price.asc(),
    "-price": Dish.price.desc(),
    "weight": Dish.weight_g.desc(),
}


class CategoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def all(self) -> list[Category]:
        stmt = select(Category).options(selectinload(Category.dishes)).order_by(Category.name)
        return list(self.session.scalars(stmt))

    def get(self, category_id: int) -> Category | None:
        return self.session.get(Category, category_id)

    def get_by_name(self, name: str) -> Category | None:
        return self.session.scalars(select(Category).where(Category.name == name)).first()

    def add(self, category: Category) -> Category:
        self.session.add(category)
        self.session.flush()
        return category

    def delete(self, category: Category) -> None:
        self.session.delete(category)
        self.session.flush()


class DishRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find(self, filters: dict[str, Any], sort: str = "name") -> list[Dish]:
        conditions = []
        if filters.get("search"):
            pattern = f"%{filters['search'].lower()}%"
            conditions.append(or_(func.lower(Dish.name).like(pattern),
                                  func.lower(Dish.description).like(pattern)))
        if filters.get("category_id"):
            conditions.append(Dish.category_id == filters["category_id"])
        if filters.get("max_price") is not None:
            conditions.append(Dish.price <= filters["max_price"])
        if filters.get("vegetarian"):
            conditions.append(Dish.is_vegetarian.is_(True))
        if filters.get("available"):
            conditions.append(Dish.is_available.is_(True))
        stmt = (select(Dish).options(selectinload(Dish.category)).where(*conditions)
                .order_by(DISH_SORTS.get(sort, Dish.name.asc()), Dish.id))
        return list(self.session.scalars(stmt))

    def get(self, dish_id: int) -> Dish | None:
        return self.session.get(Dish, dish_id)

    def get_many(self, dish_ids: list[int]) -> dict[int, Dish]:
        return {d.id: d for d in self.session.scalars(select(Dish).where(Dish.id.in_(dish_ids)))}

    def get_by_name(self, name: str) -> Dish | None:
        return self.session.scalars(select(Dish).where(Dish.name == name)).first()

    def add(self, dish: Dish) -> Dish:
        self.session.add(dish)
        self.session.flush()
        return dish

    def delete(self, dish: Dish) -> None:
        self.session.delete(dish)
        self.session.flush()

    def popular(self, limit: int = 5) -> list[tuple[Dish, int]]:
        stmt = (select(Dish, func.sum(OrderItem.quantity).label("qty"))
                .join(OrderItem).join(Order)
                .where(Order.status != OrderStatus.CANCELLED)
                .group_by(Dish.id).order_by(func.sum(OrderItem.quantity).desc()).limit(limit))
        return [(dish, int(qty)) for dish, qty in self.session.execute(stmt)]


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find(self, status: OrderStatus | None = None, search: str | None = None) -> list[Order]:
        stmt = select(Order).options(selectinload(Order.items).selectinload(OrderItem.dish))
        if status is not None:
            stmt = stmt.where(Order.status == status)
        if search:
            stmt = stmt.where(func.lower(Order.customer_name).like(f"%{search.lower()}%"))
        return list(self.session.scalars(stmt.order_by(Order.id.desc())))

    def get(self, order_id: int) -> Order | None:
        stmt = (select(Order).where(Order.id == order_id)
                .options(selectinload(Order.items).selectinload(OrderItem.dish)))
        return self.session.scalars(stmt).first()

    def add(self, order: Order) -> Order:
        self.session.add(order)
        self.session.flush()
        return order
