# Лабораторная работа №10. Вариант 5. Отель — REST API

REST API на **Flask** для ресурса **Room** и консольный клиент на **requests**.
Специализированная операция — **свободные номера** (`GET /rooms/available`).

## Запуск

```bash
pip install -r requirements.txt
python app.py        # сервер http://127.0.0.1:5000
python client.py     # консольный клиент
pytest -v            # 18 тестов
```

## Архитектура

```
client.py ──HTTP──► routes.py (Blueprint) ──► service.py ──► repository.py (память)
                     schemas.py — валидация, exceptions.py — ошибки API
```

Модель `Room`: `id`, `number`, `room_type` (standard / deluxe / suite / family), `floor`,
`capacity`, `price`, `status` (free / booked / occupied / maintenance).

## API

| Метод | Endpoint | Назначение | Успешный код |
|-------|----------|------------|--------------|
| GET | `/rooms` | список (фильтры, сортировка) | 200 |
| GET | `/rooms/{id}` | номер | 200 |
| POST | `/rooms` | создание | 201 |
| PUT | `/rooms/{id}` | полное изменение | 200 |
| PATCH | `/rooms/{id}` | частичное изменение | 200 |
| DELETE | `/rooms/{id}` | удаление | 204 |
| GET | `/rooms/available` | свободные номера, самые дешёвые первыми | 200 |
| GET | `/rooms/statistics` | загрузка отеля и средняя цена | 200 |

**Фильтры:** `room_type`, `status`, `floor`, `min_capacity`, `min_price`, `max_price`;
для `/rooms/available` — `guests`.
**Сортировка:** `sort=number|floor|capacity|price`, `order=asc|desc`.

### Примеры

```http
GET /rooms?min_price=4000&sort=price&order=desc
200 OK
[{"id": 5, "number": "301", "room_type": "suite", "floor": 3, "capacity": 4, "price": 9000.0, "status": "booked"}, ...]

GET /rooms/2
200 OK
{"id": 2, "number": "102", "room_type": "standard", "floor": 1, "capacity": 2, "price": 3200.0, "status": "occupied"}

POST /rooms
Content-Type: application/json
{"number": "401", "room_type": "deluxe", "floor": 4, "capacity": 2, "price": 5500}
201 Created, Location: /rooms/7
{"id": 7, "number": "401", "room_type": "deluxe", "floor": 4, "capacity": 2, "price": 5500.0, "status": "free"}

PUT /rooms/7
{"number": "401", "room_type": "suite", "floor": 4, "capacity": 3, "price": 8000}
200 OK

PATCH /rooms/7
{"price": 7500}
200 OK

DELETE /rooms/7
204 No Content

GET /rooms/available?guests=3
200 OK
[{"id": 4, "number": "202", "room_type": "family", "capacity": 4, "price": 6000.0, "status": "free", ...}, ...]

GET /rooms/statistics
200 OK
{"rooms_count": 6, "available_count": 4, "occupancy_percent": 33.3, "average_price": 5950.0}
```

### Ошибки

Единый формат: `{"error": "описание", "code": "КОД"}`.

| Ситуация | Код | `code` |
|----------|-----|--------|
| некорректные данные или query-параметры, тело не JSON | 400 | `VALIDATION_ERROR` |
| некорректный идентификатор (`/rooms/abc`) | 400 | `VALIDATION_ERROR` |
| номер не найден | 404 | `ROOM_NOT_FOUND` |
| неподдерживаемый метод | 405 | `METHOD_NOT_ALLOWED` |
| дублирующийся номер комнаты, удаление занятого номера | 409 | `CONFLICT` |

## Тесты

`tests/test_repository.py` (2), `tests/test_service.py` (4), `tests/test_api.py` (12).
