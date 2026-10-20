"""Репозитории: SQL-запросы к SQLite (только параметризованные)."""

from dataclasses import dataclass
from datetime import date

import aiosqlite


@dataclass
class RoomType:
    id: int
    name: str
    description: str


@dataclass
class Room:
    id: int
    number: str
    type_id: int
    type_name: str
    floor: int
    capacity: int
    price: float
    is_active: bool


@dataclass
class Client:
    id: int
    telegram_id: int
    name: str


@dataclass
class Booking:
    id: int
    client_id: int
    room_id: int
    room_number: str
    room_type: str
    check_in: date
    check_out: date
    guests: int
    total: float
    status: str

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days


ROOM_SELECT = """
    SELECT r.id, r.number, r.type_id, t.name AS type_name, r.floor, r.capacity, r.price,
           r.is_active
    FROM rooms r JOIN room_types t ON t.id = r.type_id
"""

BOOKING_SELECT = """
    SELECT b.id, b.client_id, b.room_id, r.number AS room_number, t.name AS room_type,
           b.check_in, b.check_out, b.guests, b.total, b.status
    FROM bookings b
    JOIN rooms r ON r.id = b.room_id
    JOIN room_types t ON t.id = r.type_id
"""


def _room(row) -> Room:
    return Room(**{**dict(row), "is_active": bool(row["is_active"])})


def _booking(row) -> Booking:
    data = dict(row)
    data["check_in"] = date.fromisoformat(data["check_in"])
    data["check_out"] = date.fromisoformat(data["check_out"])
    return Booking(**data)


class RoomRepository:
    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.db = connection

    async def types(self) -> list[RoomType]:
        cursor = await self.db.execute("SELECT id, name, description FROM room_types ORDER BY id")
        return [RoomType(**dict(row)) for row in await cursor.fetchall()]

    async def type_by_name(self, name: str) -> RoomType | None:
        # lower() в SQLite не работает с кириллицей, поэтому сравниваем в Python
        return next((t for t in await self.types() if t.name.casefold() == name.casefold()), None)

    async def get(self, room_id: int) -> Room | None:
        cursor = await self.db.execute(ROOM_SELECT + " WHERE r.id = ?", (room_id,))
        row = await cursor.fetchone()
        return _room(row) if row else None

    async def get_by_number(self, number: str) -> Room | None:
        cursor = await self.db.execute(ROOM_SELECT + " WHERE r.number = ?", (number,))
        row = await cursor.fetchone()
        return _room(row) if row else None

    async def all(self, type_id: int | None = None) -> list[Room]:
        sql, params = ROOM_SELECT, []
        if type_id is not None:
            sql += " WHERE r.type_id = ?"
            params.append(type_id)
        cursor = await self.db.execute(sql + " ORDER BY r.number", params)
        return [_room(row) for row in await cursor.fetchall()]

    async def free(self, check_in: date, check_out: date, guests: int,
                   type_id: int | None = None, exclude_booking: int | None = None) -> list[Room]:
        sql = ROOM_SELECT + """
            WHERE r.is_active = 1 AND r.capacity >= ?
              AND NOT EXISTS (
                  SELECT 1 FROM bookings b
                  WHERE b.room_id = r.id AND b.status = 'active' AND b.id IS NOT ?
                    AND b.check_in < ? AND b.check_out > ?)
        """
        params: list = [guests, exclude_booking, check_out.isoformat(), check_in.isoformat()]
        if type_id is not None:
            sql += " AND r.type_id = ?"
            params.append(type_id)
        cursor = await self.db.execute(sql + " ORDER BY r.price, r.number", params)
        return [_room(row) for row in await cursor.fetchall()]

    async def add(self, number: str, type_id: int, floor: int, capacity: int,
                  price: float) -> Room:
        cursor = await self.db.execute(
            "INSERT INTO rooms (number, type_id, floor, capacity, price) VALUES (?, ?, ?, ?, ?)",
            (number, type_id, floor, capacity, price))
        await self.db.commit()
        return await self.get(cursor.lastrowid)

    async def set_active(self, room_id: int, active: bool) -> None:
        await self.db.execute("UPDATE rooms SET is_active = ? WHERE id = ?", (int(active), room_id))
        await self.db.commit()

    async def count(self) -> int:
        cursor = await self.db.execute("SELECT COUNT(*) FROM rooms")
        return (await cursor.fetchone())[0]


class ClientRepository:
    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.db = connection

    async def get_or_create(self, telegram_id: int, name: str) -> Client:
        await self.db.execute(
            "INSERT INTO clients (telegram_id, name) VALUES (?, ?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET name = excluded.name", (telegram_id, name))
        await self.db.commit()
        cursor = await self.db.execute(
            "SELECT id, telegram_id, name FROM clients WHERE telegram_id = ?", (telegram_id,))
        return Client(**dict(await cursor.fetchone()))

    async def all(self) -> list[tuple[Client, int]]:
        cursor = await self.db.execute(
            "SELECT c.id, c.telegram_id, c.name, COUNT(b.id) AS bookings FROM clients c "
            "LEFT JOIN bookings b ON b.client_id = c.id GROUP BY c.id ORDER BY c.id")
        return [(Client(r["id"], r["telegram_id"], r["name"]), r["bookings"])
                for r in await cursor.fetchall()]


class BookingRepository:
    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.db = connection

    async def add(self, client_id: int, room_id: int, check_in: date, check_out: date,
                  guests: int, total: float) -> Booking:
        cursor = await self.db.execute(
            "INSERT INTO bookings (client_id, room_id, check_in, check_out, guests, total) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (client_id, room_id, check_in.isoformat(), check_out.isoformat(), guests, total))
        await self.db.commit()
        return await self.get(cursor.lastrowid)

    async def get(self, booking_id: int) -> Booking | None:
        cursor = await self.db.execute(BOOKING_SELECT + " WHERE b.id = ?", (booking_id,))
        row = await cursor.fetchone()
        return _booking(row) if row else None

    async def for_client(self, client_id: int) -> list[Booking]:
        cursor = await self.db.execute(
            BOOKING_SELECT + " WHERE b.client_id = ? ORDER BY b.check_in DESC", (client_id,))
        return [_booking(row) for row in await cursor.fetchall()]

    async def update_dates(self, booking_id: int, check_in: date, check_out: date,
                           total: float) -> Booking:
        await self.db.execute(
            "UPDATE bookings SET check_in = ?, check_out = ?, total = ? WHERE id = ?",
            (check_in.isoformat(), check_out.isoformat(), total, booking_id))
        await self.db.commit()
        return await self.get(booking_id)

    async def set_status(self, booking_id: int, status: str) -> None:
        await self.db.execute("UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id))
        await self.db.commit()

    async def delete(self, booking_id: int) -> None:
        await self.db.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        await self.db.commit()

    async def statistics(self) -> dict:
        cursor = await self.db.execute(
            "SELECT COUNT(*) AS total, SUM(status = 'active') AS active, "
            "COALESCE(SUM(CASE WHEN status = 'active' THEN total END), 0) AS revenue "
            "FROM bookings")
        row = await cursor.fetchone()
        cursor = await self.db.execute(
            "SELECT t.name, COUNT(b.id) AS cnt FROM bookings b JOIN rooms r ON r.id = b.room_id "
            "JOIN room_types t ON t.id = r.type_id WHERE b.status = 'active' "
            "GROUP BY t.id ORDER BY cnt DESC LIMIT 1")
        popular = await cursor.fetchone()
        return {"total": row["total"], "active": row["active"] or 0, "revenue": row["revenue"],
                "popular_type": popular["name"] if popular else "—"}


class ActivityRepository:
    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.db = connection

    async def log(self, telegram_id: int, action: str) -> None:
        await self.db.execute("INSERT INTO activity (telegram_id, action) VALUES (?, ?)",
                              (telegram_id, action))
        await self.db.commit()

    async def statistics(self) -> dict:
        cursor = await self.db.execute(
            "SELECT COUNT(*) AS messages, COUNT(DISTINCT telegram_id) AS users FROM activity")
        row = await cursor.fetchone()
        cursor = await self.db.execute(
            "SELECT action, COUNT(*) AS cnt FROM activity WHERE action NOT LIKE 'text:%' "
            "GROUP BY action ORDER BY cnt DESC LIMIT 1")
        top = await cursor.fetchone()
        return {"messages": row["messages"], "users": row["users"],
                "popular_action": top["action"] if top else "—"}
