"""Асинхронная работа с SQLite через aiosqlite."""

import aiosqlite

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS room_types (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS rooms (
    id          INTEGER PRIMARY KEY,
    number      TEXT    NOT NULL UNIQUE,
    type_id     INTEGER NOT NULL REFERENCES room_types(id),
    floor       INTEGER NOT NULL CHECK (floor >= 0),
    capacity    INTEGER NOT NULL CHECK (capacity > 0),
    price       REAL    NOT NULL CHECK (price > 0),
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY,
    telegram_id INTEGER NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY,
    client_id   INTEGER NOT NULL REFERENCES clients(id),
    room_id     INTEGER NOT NULL REFERENCES rooms(id),
    check_in    TEXT    NOT NULL,
    check_out   TEXT    NOT NULL,
    guests      INTEGER NOT NULL CHECK (guests > 0),
    total       REAL    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (check_out > check_in)
);

CREATE TABLE IF NOT EXISTS activity (
    id          INTEGER PRIMARY KEY,
    telegram_id INTEGER NOT NULL,
    action      TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bookings_room ON bookings(room_id, status);
CREATE INDEX IF NOT EXISTS idx_bookings_client ON bookings(client_id);
"""

ROOM_TYPES = [
    (1, "Стандарт", "Двуспальная кровать, душ, рабочий стол"),
    (2, "Комфорт", "Улучшенный номер с видом на город"),
    (3, "Семейный", "Две комнаты, детская кроватка"),
    (4, "Люкс", "Гостиная, ванна, мини-бар"),
]

# номер, тип, этаж, вместимость, цена
ROOMS = [
    ("101", 1, 1, 2, 3200), ("102", 1, 1, 2, 3200), ("103", 1, 1, 1, 2800),
    ("104", 1, 1, 2, 3300), ("105", 2, 1, 2, 4300), ("201", 2, 2, 2, 4500),
    ("202", 2, 2, 3, 4900), ("203", 1, 2, 2, 3400), ("204", 3, 2, 4, 6000),
    ("205", 3, 2, 5, 6500), ("301", 4, 3, 3, 9000), ("302", 4, 3, 2, 8500),
    ("303", 2, 3, 2, 4700), ("304", 3, 3, 4, 6200), ("305", 1, 3, 2, 3500),
    ("401", 4, 4, 4, 12000), ("402", 4, 4, 3, 11000), ("403", 2, 4, 3, 5200),
    ("404", 3, 4, 5, 7000), ("405", 1, 4, 2, 3600),
]


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self.connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.connection = await aiosqlite.connect(self.path)
        self.connection.row_factory = aiosqlite.Row
        await self.connection.executescript(SCHEMA)
        await self.connection.commit()

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
            self.connection = None

    async def seed(self) -> bool:
        """Заполняет справочники и номера, если БД пустая (24 записи)."""
        cursor = await self.connection.execute("SELECT COUNT(*) FROM rooms")
        if (await cursor.fetchone())[0]:
            return False
        await self.connection.executemany(
            "INSERT INTO room_types (id, name, description) VALUES (?, ?, ?)", ROOM_TYPES)
        await self.connection.executemany(
            "INSERT INTO rooms (number, type_id, floor, capacity, price) VALUES (?, ?, ?, ?, ?)",
            ROOMS)
        await self.connection.commit()
        return True
