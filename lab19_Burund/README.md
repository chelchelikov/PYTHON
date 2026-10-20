# Лабораторная работа №19. Вариант 5. Ресторан — микросервисы

Распределённое приложение ресторана: **меню**, **заказы**, **доставка** и **API Gateway**.
Событие **OrderCreated** передаётся через RabbitMQ сервису доставки, который сам создаёт
доставку и назначает курьера.

**Стек:** Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, PostgreSQL 16, RabbitMQ (aio-pika),
httpx, Docker, Docker Compose, pytest.

## Архитектура

```
                         Client
                           │ HTTP :8000
                    ┌──────▼──────┐
                    │ API Gateway │  маршрутизация, Retry (GET), Circuit Breaker, /health,
                    └──┬────┬───┬─┘  композиция /api/orders/{id}/full
          ┌────────────┘    │   └──────────────┐
   ┌──────▼──────┐  ┌───────▼──────┐  ┌────────▼────────┐
   │ menu-service│◄─┤ order-service│  │ delivery-service│
   └──────┬──────┘  └──┬────────┬──┘  └───────┬───▲────┘
          │  HTTP: Retry + CB   │ OrderCreated │   │ order.*
       menu-db       orders-db  └──► RabbitMQ ─────┘
                                  (topic exchange restaurant.events)      delivery-db
```

| Сервис | Ответственность | БД | API |
|--------|-----------------|----|-----|
| `menu-service` | блюда, цены, доступность | `menu_db` | `GET/POST /dishes`, `GET/PUT/PATCH/DELETE /dishes/{id}`, `GET /dishes?ids=1,2` |
| `order-service` | заказы; проверяет блюда в меню, публикует `OrderCreated` / `OrderCancelled` | `orders_db` | `GET/POST /orders`, `GET/PUT/DELETE /orders/{id}` |
| `delivery-service` | доставки; подписан на `order.*`, назначает курьера и время доставки | `delivery_db` | `GET/POST /deliveries`, `GET/PUT/DELETE /deliveries/{id}`, `GET /deliveries/by-order/{order_id}` |
| `gateway` | единая точка входа | — | `/api/dishes…`, `/api/orders…`, `/api/deliveries…`, `/api/orders/{id}/full`, `/health` |

У всех сервисов есть `GET /health`.

## Запуск

```bash
cp .env.example .env          # пароли БД и RabbitMQ
docker compose up --build     # 8 контейнеров: gateway, 3 сервиса, 3 PostgreSQL, RabbitMQ
```

- Gateway и Swagger: <http://localhost:8000/docs>
- Состояние системы: <http://localhost:8000/health>
- RabbitMQ: <http://localhost:15672> (логин и пароль из `.env`)

Тесты каждого сервиса запускаются из его папки:

```bash
cd order-service && pip install -r requirements.txt && pytest -v
```

Без Docker каждый сервис можно запустить через `uvicorn app.main:app --port 800X`; без
`DATABASE_URL` используется SQLite, без `BROKER_URL` — брокер в памяти.

## Паттерны

### API Gateway

Все запросы клиента идут через `gateway`, который проксирует `/api/<ресурс>/…` нужному
сервису, передаёт заголовок `X-Request-ID` (сквозной идентификатор запроса в логах всех
сервисов) и собирает ответ из двух сервисов: `GET /api/orders/{id}/full` возвращает заказ
и доставку; если delivery-service недоступен — частичный ответ.

### Database per Service

Каждый сервис работает только со своей БД (`menu-db`, `orders-db`, `delivery-db`), каждая
БД находится в отдельной docker-сети, доступной только её сервису. Order Service не читает
таблицы меню: он получает блюда по HTTP и сохраняет копию названия и цены в позиции заказа.

### Retry

`order-service/app/resilience.py → retry()`: до 3 попыток, тайм-аут запроса 2 с, задержка
0,2 с с удвоением (0,2 → 0,4), повтор только для временных ошибок (сетевые ошибки,
тайм-аут, 5xx). После последней попытки — `ServiceUnavailable` → клиент получает 503.
Gateway повторяет только GET: повтор POST мог бы создать заказ дважды.

Демонстрация: `POST /admin/faults {"fail_next": 2}` в menu-service — следующие два запроса
к меню вернут 503. Заказ всё равно создаётся, а в логе order-service видно:

```
resilience WARNING menu-service: попытка 1/3 неудачна (HTTP 503), повтор через 0.2 с
resilience WARNING menu-service: попытка 2/3 неудачна (HTTP 503), повтор через 0.4 с
order-service INFO request_id=... POST /orders status=201
```

### Circuit Breaker

`CircuitBreaker`: после 3 неудач подряд — **OPEN**, запросы сразу отклоняются без обращения
к сервису; через `recovery_timeout` — **HALF_OPEN** и один пробный запрос; успех → **CLOSED**,
неудача → снова OPEN. Используется в order-service (вызовы меню) и в gateway (отдельный
выключатель на каждый сервис). Проверено на запущенной системе (`docker compose stop menu-service`):

```
{"detail":"menu-service: сервис недоступен ([Errno -2] Name or service not known)"}   ×3
{"detail":"menu-service: Circuit Breaker разомкнут (OPEN), запрос не отправлен"}
GET /health → {"status":"degraded", "menu-service": {"status":"unavailable"}, ...}
... menu-service снова запущен:
CircuitBreaker[menu-service]: OPEN -> HALF_OPEN, пробный запрос
CircuitBreaker[menu-service]: сервис восстановлен -> CLOSED
```

Gateway считает сбоем сервиса только сетевые ошибки и ответы 502/504. Ответ 503 от живого
order-service (у которого недоступно меню) передаётся клиенту как есть. Иначе отказ меню
размыкал бы выключатель order-service, и перестал бы работать даже просмотр заказов
(каскадный отказ). Эта ошибка была найдена при ручной проверке и закрыта тестом
`test_dependency_failure_does_not_open_neighbour_circuit`.

### Асинхронное взаимодействие (RabbitMQ)

1. **Создание события:** `OrderService.create` после сохранения заказа формирует
   `{"event": "OrderCreated", "order_id", "customer_name", "phone", "address", "total", "items"}`.
2. **Отправка:** `RabbitMQPublisher` публикует его в topic exchange `restaurant.events` с
   ключом `order.created` (persistent-сообщение).
3. **Получение:** `delivery-service/app/consumer.py` слушает очередь
   `delivery-service.order-events` (привязка `order.*`), подтверждает сообщения вручную.
4. **Действие:** `DeliveryService.handle_event` создаёт доставку, назначает наименее
   загруженного курьера, считает время (30 мин + 5 мин на позицию). Обработка идемпотентна:
   повторное событие не создаёт вторую доставку. `OrderCancelled` (`DELETE /orders/{id}`)
   отменяет доставку.

Некорректное сообщение отбрасывается, при временной ошибке (например, недоступна БД)
сообщение возвращается в очередь. Если брокер ещё не запущен, consumer переподключается.

## Наблюдаемость

Каждый сервис пишет в журнал время, имя сервиса, request id, метод, путь, статус и
длительность:

```
2026-10-20 12:31:04,231 order-service INFO request_id=deeb5e79496d POST /orders status=201 duration=120ms
```

`GET /health` у gateway показывает состояние каждого сервиса и его Circuit Breaker.

## Тесты

| Сервис | Unit | Интеграционные (HTTP + БД) | Взаимодействие | Недоступность | Всего |
|--------|-----:|---------------------------:|----------------|---------------|------:|
| menu-service | 5 | 3 | контракт `GET /dishes?ids` для order-service | `/health` при недоступной БД | 10 |
| order-service | 5 (Retry, Circuit Breaker, событие) | 3 (CRUD и отмена, отклонённые заказы, Retry) | вызов меню через `httpx.MockTransport` + публикация события | меню упало → 503, Circuit Breaker OPEN | 10 |
| delivery-service | 5 | 2 | обработка `OrderCreated` / `OrderCancelled` в формате order-service | брокер недоступен — consumer не падает | 10 |
| gateway | — | 4 (маршрутизация, тело POST, 404, POST без повторов) | маршрутизация, композиция заказа и доставки | сервис упал → OPEN; зависимость упала → выключатель соседа не размыкается | 8 |

Всего 38 тестов. Mock используется там, где нужно изолировать сервис от соседей
(`httpx.MockTransport`, брокер в памяти, `monkeypatch` для aio-pika).
