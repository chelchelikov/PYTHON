from typing import Any

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.room import Room

SORT_COLUMNS = {"number": Room.number, "price": Room.price, "floor": Room.floor,
                "capacity": Room.capacity}


class RoomRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, room_id: int) -> Room | None:
        return self.session.get(Room, room_id)

    def get_by_number(self, number: str) -> Room | None:
        return self.session.scalars(select(Room).where(Room.number == number)).first()

    @staticmethod
    def _conditions(filters: dict[str, Any]) -> list:
        conditions = []
        if filters.get("room_type"):
            conditions.append(Room.room_type == filters["room_type"])
        if filters.get("min_price") is not None:
            conditions.append(Room.price >= filters["min_price"])
        if filters.get("max_price") is not None:
            conditions.append(Room.price <= filters["max_price"])
        if filters.get("is_available") is not None:
            conditions.append(Room.is_available.is_(filters["is_available"]))
        if filters.get("min_capacity") is not None:
            conditions.append(Room.capacity >= filters["min_capacity"])
        if filters.get("floor") is not None:
            conditions.append(Room.floor == filters["floor"])
        return conditions

    def list_rooms(self, filters: dict[str, Any], sort: str, descending: bool, limit: int,
             offset: int) -> tuple[int, list[Room]]:
        conditions = self._conditions(filters)
        total = self.session.scalar(select(func.count(Room.id)).where(*conditions))
        column = SORT_COLUMNS[sort]
        stmt = (select(Room).where(*conditions)
                .order_by(column.desc() if descending else column.asc(), Room.id)
                .offset(offset).limit(limit))
        return total, list(self.session.scalars(stmt))

    def search(self, text: str, limit: int) -> list[Room]:
        """Поиск по номеру комнаты, типу или удобству (подстрока, без учёта регистра)."""
        pattern = f"%{text.lower()}%"
        stmt = (select(Room)
                .where(or_(func.lower(Room.number).like(pattern),
                           func.lower(Room.room_type).like(pattern),
                           func.lower(cast(Room.amenities, String))
                           .like(pattern)))
                .order_by(Room.number).limit(limit))
        return list(self.session.scalars(stmt))

    def add(self, room: Room) -> Room:
        self.session.add(room)
        self.session.commit()
        self.session.refresh(room)
        return room

    def save(self, room: Room) -> Room:
        self.session.commit()
        self.session.refresh(room)
        return room

    def delete(self, room: Room) -> None:
        self.session.delete(room)
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def statistics(self) -> dict[str, Any]:
        row = self.session.execute(
            select(func.count(Room.id), func.coalesce(func.avg(Room.price), 0),
                   func.coalesce(func.min(Room.price), 0), func.coalesce(func.max(Room.price), 0),
                   func.coalesce(func.sum(Room.capacity), 0))).one()
        available = self.session.scalar(
            select(func.count(Room.id)).where(Room.is_available.is_(True)))
        by_type = self.session.execute(
            select(Room.room_type, func.count(Room.id), func.avg(Room.price))
            .group_by(Room.room_type).order_by(Room.room_type)).all()
        return {"total": row[0], "available": available, "average_price": float(row[1]),
                "min_price": float(row[2]), "max_price": float(row[3]),
                "total_capacity": int(row[4]),
                "by_type": [{"room_type": t, "count": c, "average_price": round(float(a), 2)}
                            for t, c, a in by_type]}
