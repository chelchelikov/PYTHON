-- Лабораторная работа №11. Вариант 5. Отель — схема БД (SQLite)
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS booking_rooms;
DROP TABLE IF EXISTS bookings;
DROP TABLE IF EXISTS guests;
DROP TABLE IF EXISTS room_amenities;
DROP TABLE IF EXISTS amenities;
DROP TABLE IF EXISTS room_photos;
DROP TABLE IF EXISTS rooms;
DROP TABLE IF EXISTS room_types;

-- Тип номера (1:N с rooms)
CREATE TABLE room_types (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    description TEXT
);

-- Номер — основная сущность
CREATE TABLE rooms (
    id        INTEGER PRIMARY KEY,
    number    TEXT    NOT NULL UNIQUE,
    type_id   INTEGER NOT NULL REFERENCES room_types(id),
    floor     INTEGER NOT NULL CHECK (floor >= 0),
    capacity  INTEGER NOT NULL CHECK (capacity > 0),
    price     REAL    NOT NULL CHECK (price > 0),
    status    TEXT    NOT NULL DEFAULT 'free'
              CHECK (status IN ('free', 'booked', 'occupied', 'maintenance'))
);

-- Фотографии номера: в БД хранится только путь, сами файлы отдаёт CDN (1:N)
CREATE TABLE room_photos (
    id       INTEGER PRIMARY KEY,
    room_id  INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    path     TEXT    NOT NULL,
    is_main  INTEGER NOT NULL DEFAULT 0 CHECK (is_main IN (0, 1))
);

-- Удобства и связь N:M с номерами
CREATE TABLE amenities (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
);

CREATE TABLE room_amenities (
    room_id    INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    amenity_id INTEGER NOT NULL REFERENCES amenities(id) ON DELETE CASCADE,
    PRIMARY KEY (room_id, amenity_id)
);

CREATE TABLE guests (
    id     INTEGER PRIMARY KEY,
    name   TEXT NOT NULL,
    email  TEXT NOT NULL UNIQUE,
    phone  TEXT
);

-- Бронирование: гость 1:N бронирований
CREATE TABLE bookings (
    id          INTEGER PRIMARY KEY,
    guest_id    INTEGER NOT NULL REFERENCES guests(id),
    check_in    TEXT    NOT NULL,
    check_out   TEXT    NOT NULL,
    total_cost  REAL    NOT NULL CHECK (total_cost >= 0),
    status      TEXT    NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'completed', 'cancelled')),
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (check_out > check_in)
);

-- Одно бронирование может включать несколько номеров (N:M)
CREATE TABLE booking_rooms (
    booking_id  INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    room_id     INTEGER NOT NULL REFERENCES rooms(id),
    guests      INTEGER NOT NULL CHECK (guests > 0),
    price       REAL    NOT NULL CHECK (price > 0),
    PRIMARY KEY (booking_id, room_id)
);

-- Индексы
-- Поиск свободных номеров фильтрует по статусу и вместимости, сортирует по цене
CREATE INDEX idx_rooms_status_capacity ON rooms(status, capacity);
-- Фильтр по типу номера и JOIN rooms ↔ room_types
CREATE INDEX idx_rooms_type ON rooms(type_id);
-- История бронирований гостя
CREATE INDEX idx_bookings_guest ON bookings(guest_id);
-- Проверка пересечения периодов бронирования номера
CREATE INDEX idx_booking_rooms_room ON booking_rooms(room_id);
