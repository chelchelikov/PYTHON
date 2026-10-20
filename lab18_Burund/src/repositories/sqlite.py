import sqlite3
from datetime import date

from src.models import Booking, BookingStatus, Room

SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    id              INTEGER PRIMARY KEY,
    number          TEXT NOT NULL UNIQUE,
    room_type       TEXT NOT NULL,
    capacity        INTEGER NOT NULL CHECK (capacity > 0),
    price_per_night REAL NOT NULL CHECK (price_per_night > 0)
);
CREATE TABLE IF NOT EXISTS bookings (
    id         INTEGER PRIMARY KEY,
    room_id    INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    guest_name TEXT NOT NULL,
    check_in   TEXT NOT NULL,
    check_out  TEXT NOT NULL,
    guests     INTEGER NOT NULL,
    total      REAL NOT NULL,
    status     TEXT NOT NULL DEFAULT 'active'
);
"""


def connect(path: str = ":memory:") -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection


class RoomRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.db = connection

    @staticmethod
    def _to_room(row: sqlite3.Row) -> Room:
        return Room(row["number"], row["room_type"], row["capacity"], row["price_per_night"],
                    row["id"])

    def add(self, room: Room) -> Room:
        cursor = self.db.execute(
            "INSERT INTO rooms (number, room_type, capacity, price_per_night) VALUES (?, ?, ?, ?)",
            (room.number, room.room_type, room.capacity, room.price_per_night))
        self.db.commit()
        room.id = cursor.lastrowid
        return room

    def get(self, room_id: int) -> Room | None:
        row = self.db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
        return self._to_room(row) if row else None

    def get_by_number(self, number: str) -> Room | None:
        row = self.db.execute("SELECT * FROM rooms WHERE number = ?", (number,)).fetchone()
        return self._to_room(row) if row else None

    def list(self, min_capacity: int = 1) -> list[Room]:
        rows = self.db.execute("SELECT * FROM rooms WHERE capacity >= ? ORDER BY price_per_night, "
                               "number", (min_capacity,)).fetchall()
        return [self._to_room(row) for row in rows]

    def update(self, room: Room) -> Room:
        self.db.execute("UPDATE rooms SET number = ?, room_type = ?, capacity = ?, "
                        "price_per_night = ? WHERE id = ?",
                        (room.number, room.room_type, room.capacity, room.price_per_night,
                         room.id))
        self.db.commit()
        return room

    def delete(self, room_id: int) -> None:
        # Отменённые брони номера удаляются каскадно (ON DELETE CASCADE);
        # наличие активных броней проверяет RoomService до вызова delete()
        self.db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        self.db.commit()


class BookingRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.db = connection

    @staticmethod
    def _to_booking(row: sqlite3.Row) -> Booking:
        return Booking(row["room_id"], row["guest_name"], date.fromisoformat(row["check_in"]),
                       date.fromisoformat(row["check_out"]), row["guests"], row["total"],
                       BookingStatus(row["status"]), row["id"])

    def add(self, booking: Booking) -> Booking:
        cursor = self.db.execute(
            "INSERT INTO bookings (room_id, guest_name, check_in, check_out, guests, total, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (booking.room_id, booking.guest_name, booking.check_in.isoformat(),
             booking.check_out.isoformat(), booking.guests, booking.total, booking.status.value))
        self.db.commit()
        booking.id = cursor.lastrowid
        return booking

    def get(self, booking_id: int) -> Booking | None:
        row = self.db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        return self._to_booking(row) if row else None

    def active_for_room(self, room_id: int) -> list[Booking]:
        rows = self.db.execute("SELECT * FROM bookings WHERE room_id = ? AND status = 'active' "
                               "ORDER BY check_in", (room_id,)).fetchall()
        return [self._to_booking(row) for row in rows]

    def for_guest(self, guest_name: str) -> list[Booking]:
        rows = self.db.execute("SELECT * FROM bookings WHERE guest_name = ? ORDER BY check_in",
                               (guest_name,)).fetchall()
        return [self._to_booking(row) for row in rows]

    def update_status(self, booking_id: int, status: BookingStatus) -> None:
        self.db.execute("UPDATE bookings SET status = ? WHERE id = ?", (status.value, booking_id))
        self.db.commit()
