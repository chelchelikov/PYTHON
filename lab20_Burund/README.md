# Лабораторная работа №20. Вариант 5. Ресторан — контейнеризация и CI/CD

Микросервисная система ресторана из лабораторной №19 (меню, заказы, доставка, API Gateway,
RabbitMQ), полностью запускаемая в Docker Compose, с production-образами, автоматической
проверкой API и CI-пайплайном GitHub Actions.

**Технологии:** Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 16, RabbitMQ 3.13, httpx,
aio-pika, Docker (multi-stage), Docker Compose, pytest, pytest-cov, ruff, GitHub Actions.

## Архитектура

```
Client ──► gateway :8000 ──┬──► menu-service ──► menu-db (volume menu-data)
                           ├──► order-service ─► orders-db (volume orders-data)
                           │        │ OrderCreated / OrderCancelled
                           │        ▼
                           │     broker (RabbitMQ, volume broker-data)
                           │        ▼
                           └──► delivery-service ► delivery-db (volume delivery-data)

api-tests (профиль test) ──► gateway — автоматическая проверка API
```

Сети: `frontend` (gateway и api-tests), `backend` (gateway, сервисы, брокер) и отдельная сеть
для каждой БД — её видит только свой сервис.

## Требования

Docker 24+ с Docker Compose v2. Для запуска тестов без Docker — Python 3.12.

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `MENU_DB_PASSWORD`, `ORDERS_DB_PASSWORD`, `DELIVERY_DB_PASSWORD` | пароли баз данных сервисов (обязательны) |
| `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | учётная запись RabbitMQ |
| `GATEWAY_PORT` | внешний порт gateway (по умолчанию 8000) |
| `RABBITMQ_UI_PORT` | порт веб-интерфейса RabbitMQ (по умолчанию 15672) |

Пароли не хранятся в коде: локально они задаются в `.env` (файл в `.gitignore`, образец —
`.env.example`), в CI — через Secrets репозитория. Если пароль не задан, `docker compose`
останавливается с ошибкой `задайте в .env`.

## Запуск

```bash
cp .env.example .env              # и задать свои пароли
docker compose up --build -d      # сборка и запуск 8 контейнеров
docker compose ps                 # все сервисы должны быть healthy
```

- API и Swagger: <http://localhost:8000/docs>
- Состояние системы: <http://localhost:8000/health>
- RabbitMQ: <http://localhost:15672>

Остановка с сохранением данных: `docker compose down`. Полная очистка вместе с томами:
`docker compose down -v`.

## Docker-образы

Каждый сервис собирается из своего `Dockerfile` в два этапа:

1. **builder** — `pip wheel` собирает колёса всех зависимостей из `requirements.txt` с
   точно зафиксированными версиями;
2. **production** — чистый `python:3.12-slim`, в него ставятся только готовые колёса, код
   копируется от имени непривилегированного пользователя `appuser` (uid 10001),
   `PYTHONDONTWRITEBYTECODE`, `PYTHONUNBUFFERED`, `HEALTHCHECK` на `/health` (через
   `urllib`, т.к. curl в slim-образе нет), запуск `uvicorn app.main:app`.

В образ не попадают тесты, кэш, `.env`, `.git` и dev-зависимости (`.dockerignore`).
Тестовые и dev-зависимости вынесены в `requirements-dev.txt`.

```bash
docker build -t restaurant/order-service ./order-service    # сборка одного образа
docker compose build                                         # сборка всех образов
```

| Образ | Размер |
|-------|-------:|
| restaurant/gateway | 257 MB |
| restaurant/menu-service | 340 MB |
| restaurant/order-service | 351 MB |
| restaurant/delivery-service | 348 MB |

## Healthcheck и логирование

- У сервисов — `HEALTHCHECK` в Dockerfile (`GET /health` проверяет и подключение к БД),
  у PostgreSQL — `pg_isready`, у RabbitMQ — `rabbitmq-diagnostics ping`.
- `depends_on: condition: service_healthy` — сервисы стартуют только после готовности
  своих БД и брокера, gateway — после всех сервисов.
- `restart: unless-stopped` — автоматический перезапуск после сбоя.
- Логи (время, сервис, request id, метод, путь, статус, длительность) пишутся в stdout и
  собираются драйвером `json-file` с ротацией (10 МБ × 3 файла): `docker compose logs -f order-service`.

## Сохранение данных

Данные БД и брокера лежат в именованных томах `menu-data`, `orders-data`, `delivery-data`,
`broker-data`. Проверено: созданное блюдо остаётся доступным после `docker compose down` и
повторного `docker compose up` (этот же сценарий выполняется в CI).

## Тесты

Unit- и интеграционные тесты каждого сервиса (38 тестов) запускаются из папки сервиса:

```bash
cd order-service
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest -v --cov=app --cov-fail-under=80
```

| Сервис | Тестов | Покрытие |
|--------|-------:|---------:|
| menu-service | 10 | 98 % |
| order-service | 10 | 92 % |
| delivery-service | 10 | 89 % |
| gateway | 8 | 94 % |

### Автоматическая проверка API

`api-tests/test_api.py` проверяет работающую систему через gateway (7 тестов): health всех
сервисов, проброс `X-Request-ID`, CRUD меню, ошибки валидации и 404, отклонение заказа с
несуществующим блюдом, создание доставки по событию `OrderCreated` и её отмену по
`OrderCancelled`.

```bash
docker compose up -d --wait
docker compose --profile test run --rm api-tests
# или без контейнера: GATEWAY_URL=http://localhost:8000 pytest api-tests
```

## API

| Метод | URL (через gateway) | Назначение |
|-------|---------------------|------------|
| GET, POST | `/api/dishes` | меню, новое блюдо |
| GET, PUT, PATCH, DELETE | `/api/dishes/{id}` | блюдо |
| GET, POST | `/api/orders` | заказы, новый заказ |
| GET, PUT, DELETE | `/api/orders/{id}` | заказ; DELETE — отмена |
| GET | `/api/orders/{id}/full` | заказ вместе с доставкой |
| GET, POST | `/api/deliveries` | доставки |
| GET, PUT, DELETE | `/api/deliveries/{id}` | доставка |
| GET | `/api/deliveries/by-order/{order_id}` | доставка заказа |
| GET | `/health` | состояние всех сервисов и их Circuit Breaker |

## CI pipeline

Файл `.github/workflows/lab20-ci.yml` в корне репозитория. Запускается при `push` и
`pull_request`, если изменились файлы `lab20_Burund/**`, а также вручную.

```
lint-test (параллельно для 4 сервисов)          docker (только если lint-test зелёный)
  Checkout                                         Checkout
  Python 3.12 + кэш pip                            docker compose build
  pip install -r requirements-dev.txt              docker compose up -d --wait
  ruff check, ruff format --check                  api-tests (автопроверка API)
  pytest --cov-fail-under=80                       проверка сохранности данных после down/up
                                                   логи при ошибке, down -v
```

Если линтер или тесты падают, задание `docker` не запускается и пайплайн считается
неуспешным. Пароли для CI берутся из Secrets репозитория (`MENU_DB_PASSWORD` и др.), а если
они не заданы — из тестовых значений по умолчанию.
