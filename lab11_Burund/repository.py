"""Репозитории: весь SQL приложения, только параметризованные запросы."""

import sqlite3
from datetime import date
from typing import Any

from database import Database
from exceptions import BookingError, BookingNotFoundError, ConflictError, RoomNotFoundError
from models import Booking, BookingItem, Room

ROOM_SELECT = """
    SELECT r.id, r.number, t.code AS room_type, r.floor, r.capacity, r.price, r.status
    FROM rooms r
    JOIN room_types t ON t.id = r.type_id
"""

# Номер свободен на период, если нет активной брони, пересекающейся с ним
NO_OVERLAP = """
    NOT EXISTS (
        SELECT 1 FROM booking_rooms br
        JOIN bookings b ON b.id = br.booking_id
        WHERE br.room_id = r.id AND b.status = 'active'
          AND b.check_in < ? AND b.check_out > ?)
"""

SORT_COLUMNS = {"id": "r.id", "number": "r.number", "floor": "r.floor",
                "capacity": "r.capacity", "price": "r.price"}


class RoomRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _load_details(connection: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[Room]:
        rooms = [Room(**dict(row)) for row in rows]
        if not rooms:
            return rooms
        by_id = {room.id: room for room in rooms}
        placeholders = ",".join("?" * len(by_id))
        for row in connection.execute(
                f"SELECT ra.room_id, a.name FROM room_amenities ra "
                f"JOIN amenities a ON a.id = ra.amenity_id "
                f"WHERE ra.room_id IN ({placeholders}) ORDER BY a.name", list(by_id)):
            by_id[row["room_id"]].amenities.append(row["name"])
        for row in connection.execute(
                f"SELECT room_id, path FROM room_photos WHERE room_id IN ({placeholders}) "
                f"ORDER BY is_main DESC, id", list(by_id)):
            by_id[row["room_id"]].photos.append(row["path"])
        return rooms

    def _select(self, where: list[str], params: list[Any], sort: str | None = None,
                descending: bool = False) -> list[Room]:
        # В SQL подставляются только имена из белого списка, значения — через параметры
        sql = ROOM_SELECT
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {SORT_COLUMNS[sort or 'id']} {'DESC' if descending else 'ASC'}, r.id"
        with self.db.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
            return self._load_details(connection, rows)

    @staticmethod
    def _filters(query: dict[str, Any]) -> tuple[list[str], list[Any]]:
        where, params = [], []
        conditions = {
            "room_type": "t.code = ?", "status": "r.status = ?", "floor": "r.floor = ?",
            "min_capacity": "r.capacity >= ?", "min_price": "r.price >= ?",
            "max_price": "r.price <= ?",
        }
        for key, condition in conditions.items():
            if key in query:
                where.append(condition)
                params.append(query[key])
        if "amenity" in query:
            where.append("EXISTS (SELECT 1 FROM room_amenities ra JOIN amenities a "
                         "ON a.id = ra.amenity_id WHERE ra.room_id = r.id AND a.name = ?)")
            params.append(query["amenity"])
        return where, params

    def get_all(self, query: dict[str, Any] | None = None) -> list[Room]:
        query = query or {}
        where, params = self._filters(query)
        return self._select(where, params, query.get("sort"), query.get("descending", False))

    def get_by_id(self, room_id: int) -> Room:
        rooms = self._select(["r.id = ?"], [room_id])
        if not rooms:
            raise RoomNotFoundError(f"Номер с id={room_id} не найден")
        return rooms[0]

    def find_available(self, query: dict[str, Any]) -> list[Room]:
        """Специализированный запрос: свободные номера (на период, если он задан)."""
        query = dict(query)
        if "guests" in query:
            query["min_capacity"] = max(query.pop("guests"), query.get("min_capacity", 1))
        query.pop("status", None)
        where, params = self._filters(query)
        if "check_in" in query:
            where += ["r.status <> 'maintenance'", NO_OVERLAP]
            params += [query["check_out"].isoformat(), query["check_in"].isoformat()]
        else:
            where.append("r.status = 'free'")
        return self._select(where, params, query.get("sort") or "price",
                            query.get("descending", False))

    @staticmethod
    def _type_id(connection: sqlite3.Connection, code: str) -> int:
        row = connection.execute("SELECT id FROM room_types WHERE code = ?", (code,)).fetchone()
        return row["id"]

    @staticmethod
    def _save_amenities(connection: sqlite3.Connection, room_id: int, names: list[str]) -> None:
        connection.execute("DELETE FROM room_amenities WHERE room_id = ?", (room_id,))
        for name in names:
            connection.execute("INSERT OR IGNORE INTO amenities (name) VALUES (?)", (name,))
            connection.execute(
                "INSERT INTO room_amenities (room_id, amenity_id) "
                "SELECT ?, id FROM amenities WHERE name = ?", (room_id, name))

    def create(self, fields: dict[str, Any]) -> Room:
        try:
            with self.db.transaction() as connection:
                cursor = connection.execute(
                    "INSERT INTO rooms (number, type_id, floor, capacity, price, status) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (fields["number"], self._type_id(connection, fields["room_type"]),
                     fields["floor"], fields["capacity"], fields["price"],
                     fields.get("status", "free")))
                room_id = cursor.lastrowid
                self._save_amenities(connection, room_id, fields.get("amenities", []))
        except sqlite3.IntegrityError:
            raise ConflictError(f"Номер {fields['number']} уже существует") from None
        return self.get_by_id(room_id)

    def update(self, room_id: int, fields: dict[str, Any]) -> Room:
        self.get_by_id(room_id)
        columns = {"number": "number = ?", "floor": "floor = ?", "capacity": "capacity = ?",
                   "price": "price = ?", "status": "status = ?"}
        try:
            with self.db.transaction() as connection:
                sets = [columns[k] for k in columns if k in fields]
                params = [fields[k] for k in columns if k in fields]
                if "room_type" in fields:
                    sets.append("type_id = ?")
                    params.append(self._type_id(connection, fields["room_type"]))
                if sets:
                    connection.execute(f"UPDATE rooms SET {', '.join(sets)} WHERE id = ?",
                                       params + [room_id])
                if "amenities" in fields:
                    self._save_amenities(connection, room_id, fields["amenities"])
        except sqlite3.IntegrityError:
            raise ConflictError(f"Номер {fields.get('number')} уже существует") from None
        return self.get_by_id(room_id)

    def delete(self, room_id: int) -> None:
        self.get_by_id(room_id)
        try:
            with self.db.transaction() as connection:
                connection.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        except sqlite3.IntegrityError:
            raise ConflictError("У номера есть бронирования — удалить его нельзя") from None

    def statistics(self) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total, SUM(status = 'free') AS free, "
                "ROUND(AVG(price), 2) AS avg_price FROM rooms").fetchone()
            by_type = connection.execute(
                "SELECT t.code, COUNT(r.id) AS cnt FROM room_types t "
                "LEFT JOIN rooms r ON r.type_id = t.id GROUP BY t.id ORDER BY t.id").fetchall()
            revenue = connection.execute(
                "SELECT COALESCE(SUM(total_cost), 0) FROM bookings "
                "WHERE status <> 'cancelled'").fetchone()[0]
        total = row["total"] or 0
        free = row["free"] or 0
        return {
            "rooms_count": total,
            "available_count": free,
            "occupancy_percent": round((1 - free / total) * 100, 1) if total else 0.0,
            "average_price": row["avg_price"] or 0.0,
            "rooms_by_type": {r["code"]: r["cnt"] for r in by_type},
            "revenue": revenue,
        }


class BookingRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, guest: dict[str, Any], check_in: date, check_out: date,
               rooms: list[dict[str, int]]) -> int:
        """Бронирование нескольких номеров одной транзакцией.

        Если хотя бы один номер недоступен — ROLLBACK, в БД не остаётся ни гостя,
        ни брони, ни строк booking_rooms.
        """
        nights = (check_out - check_in).days
        with self.db.transaction() as connection:
            row = connection.execute("SELECT id FROM guests WHERE email = ?",
                                     (guest["email"],)).fetchone()
            if row:
                guest_id = row["id"]
            else:
                guest_id = connection.execute(
                    "INSERT INTO guests (name, email, phone) VALUES (?, ?, ?)",
                    (guest["name"], guest["email"], guest.get("phone"))).lastrowid

            booking_id = connection.execute(
                "INSERT INTO bookings (guest_id, check_in, check_out, total_cost) "
                "VALUES (?, ?, ?, 0)",
                (guest_id, check_in.isoformat(), check_out.isoformat())).lastrowid

            total = 0.0
            for item in rooms:
                room = connection.execute(
                    f"SELECT r.id, r.number, r.capacity, r.price, r.status FROM rooms r "
                    f"WHERE r.id = ? AND {NO_OVERLAP}",
                    (item["room_id"], check_out.isoformat(), check_in.isoformat())).fetchone()
                if room is None:
                    exists = connection.execute("SELECT 1 FROM rooms WHERE id = ?",
                                                (item["room_id"],)).fetchone()
                    if not exists:
                        raise RoomNotFoundError(f"Номер с id={item['room_id']} не найден")
                    raise BookingError(f"Номер id={item['room_id']} уже забронирован на эти даты")
                if room["status"] == "maintenance":
                    raise BookingError(f"Номер {room['number']} на обслуживании")
                if item["guests"] > room["capacity"]:
                    raise BookingError(f"Номер {room['number']} рассчитан на "
                                       f"{room['capacity']} гостей")
                connection.execute(
                    "INSERT INTO booking_rooms (booking_id, room_id, guests, price) "
                    "VALUES (?, ?, ?, ?)", (booking_id, room["id"], item["guests"], room["price"]))
                total += room["price"] * nights

            connection.execute("UPDATE bookings SET total_cost = ? WHERE id = ?",
                               (round(total, 2), booking_id))
        return booking_id

    def get(self, booking_id: int) -> Booking:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT b.id, g.name, g.email, b.check_in, b.check_out, b.total_cost, b.status "
                "FROM bookings b JOIN guests g ON g.id = b.guest_id WHERE b.id = ?",
                (booking_id,)).fetchone()
            if row is None:
                raise BookingNotFoundError(f"Бронирование #{booking_id} не найдено")
            items = connection.execute(
                "SELECT br.room_id, r.number, br.guests, br.price FROM booking_rooms br "
                "JOIN rooms r ON r.id = br.room_id WHERE br.booking_id = ? ORDER BY r.number",
                (booking_id,)).fetchall()
        return Booking(row["id"], row["name"], row["email"], date.fromisoformat(row["check_in"]),
                       date.fromisoformat(row["check_out"]), row["total_cost"], row["status"],
                       [BookingItem(*item) for item in items])

    def cancel(self, booking_id: int) -> Booking:
        booking = self.get(booking_id)
        if booking.status != "active":
            raise BookingError(f"Бронирование #{booking_id} уже {booking.status}")
        with self.db.transaction() as connection:
            connection.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?",
                               (booking_id,))
        return self.get(booking_id)

    def count(self) -> int:
        with self.db.connect() as connection:
            return connection.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
