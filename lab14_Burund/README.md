# Лабораторная работа №14. Вариант 5. Отель — номера

REST API для управления номерами отеля на **FastAPI**. Данные хранятся в **PostgreSQL**
(SQLAlchemy 2.x), карточки номеров кэшируются в **Redis**.

**Технологии:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2, PostgreSQL 16,
Redis 7 (`redis.asyncio`), Uvicorn, pytest, Docker Compose.

## Установка и запуск

```bash
pip install -r requirements.txt
cp .env.example .env                 # при необходимости поменять адреса БД и Redis
python -m app.seed                   # создать таблицу и 12 демонстрационных номеров
uvicorn app.main:app --reload
```

Swagger UI: <http://127.0.0.1:8000/docs>, ReDoc: <http://127.0.0.1:8000/redoc>,
схема OpenAPI: <http://127.0.0.1:8000/openapi.json>.

### Docker

```bash
docker compose up --build            # api :8000, postgres :5432, redis :6379
```

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `APP_ENV` | `development` | окружение |
| `DATABASE_URL` | `postgresql+psycopg://hotel:hotel@localhost:5432/hotel` | строка подключения SQLAlchemy |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis; если пусто — кэш отключён |
| `CACHE_TTL` | `120` | время жизни кэша, с |
| `LOG_LEVEL` | `INFO` | уровень логирования |

## Архитектура

```
Client → FastAPI → Router (app/routers/rooms.py) → Service (app/services/room.py) → Repository (app/repositories/room.py) → PostgreSQL
                                                         └──→ Redis (app/cache.py)
```

| Слой | Файл | Ответственность |
|------|------|-----------------|
| Router | `routers/rooms.py` | HTTP: пути, параметры, коды ответа, документация |
| Schema | `schemas/room.py` | `RoomCreate`, `RoomPatch`, `RoomResponse`, `RoomListResponse`, `RoomStatistics` |
| Service | `services/room.py` | бизнес-правила, уникальность номера, кэш и инвалидация |
| Repository | `repositories/room.py` | запросы SQLAlchemy |
| Model | `models/room.py` | ORM-модель `Room` |
| Config | `config.py` | настройки из окружения |

Зависимости (сессия БД, сервис) передаются через `Depends` — Dependency Injection FastAPI.

## API

| Метод | URL | Назначение | Код |
|-------|-----|------------|-----|
| GET | `/rooms` | список с фильтрами, сортировкой и пагинацией | 200 |
| GET | `/rooms/{id}` | номер (async, кэш Redis, заголовок `X-Cache`) | 200 / 404 |
| POST | `/rooms` | создание | 201 / 409 / 422 |
| PUT | `/rooms/{id}` | полная замена | 200 / 404 / 409 / 422 |
| PATCH | `/rooms/{id}` | частичное изменение | 200 / 404 / 422 |
| DELETE | `/rooms/{id}` | удаление | 204 / 404 |
| GET | `/rooms/search?q=` | поиск по номеру, типу, удобствам | 200 |
| GET | `/rooms/statistics` | статистика | 200 |
| GET | `/health` | проверка работоспособности | 200 |

Параметры списка: `type` (standard / deluxe / suite / family), `min_price`, `max_price`,
`is_available`, `min_capacity`, `floor`, `sort` (number / price / floor / capacity),
`order` (asc / desc), `limit` (1–100, по умолчанию 10), `offset`.

### Примеры

```http
GET /rooms?type=suite&min_price=8000&sort=price&order=desc
200 OK
{"total": 3, "limit": 10, "offset": 0, "items": [
  {"id": 10, "number": "401", "room_type": "suite", "floor": 4, "capacity": 4, "price": 12000.0,
   "is_available": true, "amenities": ["bathtub", "jacuzzi", "minibar", "sea_view", "tv", "wifi"]}, ...]}

POST /rooms
{"number": "501", "room_type": "suite", "floor": 5, "capacity": 4, "price": 15000, "amenities": ["wifi", "jacuzzi"]}
201 Created, Location: /rooms/13

PATCH /rooms/7
{"price": 9500}
200 OK — остальные поля сохранены

GET /rooms/statistics
{"total": 12, "available": 9, "occupancy_percent": 25.0, "average_price": 6116.67,
 "min_price": 2800.0, "max_price": 12000.0, "total_capacity": 34, "by_type": [...]}

POST /rooms  {"number": "", "price": -5}
422 {"detail": "Ошибка валидации", "errors": [{"field": "number", "message": "..."}, ...]}
```

## Кэш Redis

`GET /rooms/{id}`: Redis → при промахе PostgreSQL → запись в Redis на `CACHE_TTL` секунд.
В ответе заголовок `X-Cache: HIT | MISS`. `PUT`, `PATCH` и `DELETE` удаляют ключ
`lab14:room:{id}` (инвалидация). Если Redis недоступен, API продолжает работать без кэша.

## Асинхронность

`GET /rooms/{id}`, `PUT`, `PATCH`, `DELETE` объявлены через `async def`. Обращения к Redis
выполняются через `await` (`redis.asyncio`): пока ждём ответ, event loop обслуживает другие
запросы. Синхронный SQLAlchemy вызывается через `run_in_threadpool`, чтобы не блокировать
event loop. Корутина — функция, объявленная через `async def`, которая выполняется
event loop'ом и может приостанавливаться на `await`. Async ускоряет только ожидание
ввода-вывода; CPU-bound вычисления от него быстрее не становятся, потому что event loop
однопоточный.

## Обработка ошибок и логирование

404 — номер не найден; 409 — дубликат номера комнаты; 422 — ошибки валидации тела и
параметров (единый формат `{"detail", "errors"}`); ошибки БД — 500 без трассировки
(подробности только в журнале). Middleware пишет в журнал метод, путь, статус и время
выполнения каждого запроса.

## Тесты

```bash
pytest -v                                                            # SQLite в памяти + fakeredis
TEST_DATABASE_URL=postgresql+psycopg://hotel:hotel@localhost/hotel_test pytest -v
```

21 тест (`test_api.py` — 16, `test_service.py` — 3, `test_repository.py` — 2): список, получение
существующего и отсутствующего номера, корректный и некорректный POST, отсутствие полей и
дубликат, PUT, PATCH, DELETE и повторное удаление, фильтрация, сортировка, пагинация, поиск,
статистика, ошибки валидации параметров, cache miss / hit / invalidation, OpenAPI.
Проверено на SQLite и PostgreSQL 16.
