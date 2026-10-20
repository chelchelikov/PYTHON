# Итоговый проект. Вариант 5. Ресторан с доставкой

Лабораторная работа №21. Законченная система ресторана: регистрация клиентов, меню,
оформление заказа, приготовление, доставка курьером. **Уровень B** (продвинутый): монолит
FastAPI + PostgreSQL + Redis + RabbitMQ + фоновый worker.

## Функциональность

- регистрация и вход по JWT, роли **USER** (просмотр меню, свои заказы, отмена) и
  **ADMIN** (меню, все заказы, статусы, доставки, статистика);
- меню с поиском, фильтрами (категория, цена, наличие), сортировкой и пагинацией,
  кэшируется в Redis;
- оформление заказа из нескольких блюд с проверкой остатков и списанием порций;
- доставка: курьер назначается фоновым worker по событию `order.created`;
- жизненный цикл заказа `created → cooking → ready → delivering → delivered`, отмена;
- статистика: выручка, средний чек, популярные блюда, заказы по статусам.

Сущности: **Customer** (`User`), **Dish**, **Order**, **OrderItem**, **Delivery**
(+ служебная `OutboxEvent`).

## Бизнес-правила (в `services/`, покрыты тестами)

1. Нельзя заказать несуществующее или снятое с продажи блюдо, а также больше порций, чем
   осталось; порции списываются атомарно (`SELECT … FOR UPDATE`) и возвращаются при отмене.
2. Минимальная сумма заказа — 500 ₽; доставка 199 ₽, бесплатно от 2000 ₽.
3. Статус меняется только по разрешённым переходам; отменить можно лишь заказ в статусе
   `created` или `cooking`; удалить — только завершённый или отменённый.
4. Пользователь видит и отменяет только свои заказы (иначе 403), администратор — любые.
5. Статус доставки синхронизирует статус заказа; завершённую доставку менять нельзя.
6. Блюдо из существующих заказов нельзя удалить — только снять с продажи.

Заказ проверяет сразу несколько сущностей: пользователя, блюда, остатки, создаёт доставку
и событие в одной транзакции.

## Архитектура

```
Client ──HTTP/JWT──► app (FastAPI): api → services → repositories → PostgreSQL
                         │ кэш меню                 └─ outbox_events (в той же транзакции)
                         ▼
                       Redis          worker: outbox relay ──► RabbitMQ ──► consumer
                                              (назначение курьера, DeliveryService)
```

Подробно — в [docs/architecture.md](docs/architecture.md): слои, модель данных, полный цикл
заказа, поведение при отказах.

Использованные паттерны: Repository, Service Layer, Dependency Injection (`Depends`),
Cache-Aside, **Transactional Outbox**, идемпотентный обработчик событий.

## Стек

Python 3.12, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2, PostgreSQL 16, Redis 7,
RabbitMQ 3.13 (aio-pika), PyJWT, pytest, pytest-cov, fakeredis, ruff, Docker, Docker Compose,
GitHub Actions.

## Требования

Docker 24+ с Compose v2. Для разработки без Docker — Python 3.12.

## Быстрый старт

```bash
git clone <repository> && cd PYTHON/lab21_Burund
cp .env.example .env        # задать пароли и JWT_SECRET
docker compose up --build
```

- Swagger: <http://localhost:8000/docs> (кнопка **Authorize** — e-mail и пароль)
- Health: <http://localhost:8000/health>
- RabbitMQ: <http://localhost:15672>
- Администратор создаётся при первом запуске из `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

### Без Docker

```bash
pip install -r requirements-dev.txt
cd src && uvicorn app.main:app --reload    # SQLite, без Redis и брокера
python -m app.worker                       # в другом терминале: события обрабатываются локально
```

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `DATABASE_URL` | строка подключения SQLAlchemy (в compose собирается из `POSTGRES_*`) |
| `REDIS_URL` | Redis для кэша меню; пусто — без кэша |
| `BROKER_URL` | RabbitMQ; пусто — worker обрабатывает события локально |
| `JWT_SECRET`, `JWT_EXPIRE_MINUTES` | подпись и срок жизни токена |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | учётная запись администратора |
| `MENU_CACHE_TTL` | время жизни кэша меню, с |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | параметры контейнеров |

Секреты задаются только в `.env` (он в `.gitignore`) или Secrets CI.

## API

| Метод | URL | Доступ | Назначение |
|-------|-----|--------|------------|
| POST | `/auth/register` | все | регистрация (201, 409 — e-mail занят) |
| POST | `/auth/login`, `/auth/token` | все | получение JWT (JSON / форма OAuth2) |
| GET | `/auth/me` | USER | текущий пользователь |
| GET | `/dishes?q=&category=&max_price=&available_only=&sort=name\|price\|-price&limit=&offset=` | все | меню (заголовок `X-Cache`) |
| GET | `/dishes/{id}` | все | блюдо |
| POST, PUT, PATCH, DELETE | `/dishes`, `/dishes/{id}` | ADMIN | управление меню |
| POST | `/orders` | USER | оформить заказ |
| GET | `/orders?status=&sort=newest\|oldest` | USER / ADMIN | свои / все заказы |
| GET | `/orders/{id}` | владелец, ADMIN | заказ с позициями и доставкой |
| POST | `/orders/{id}/cancel` | владелец, ADMIN | отмена |
| PATCH | `/orders/{id}/status` | ADMIN | смена статуса |
| DELETE | `/orders/{id}` | ADMIN | удаление завершённого заказа |
| GET, PATCH | `/deliveries`, `/deliveries/{id}` | ADMIN | доставки, курьер, статус |
| GET | `/stats` | ADMIN | статистика |
| GET | `/health` | все | БД, Redis, размер очереди outbox |

Ошибки возвращаются в едином формате `{"error": "КОД", "message": "..."}`: 401
(`NOT_AUTHENTICATED`, `INVALID_TOKEN`, `INVALID_CREDENTIALS`), 403 (`ADMIN_ONLY`,
`NOT_YOUR_ORDER`), 404 (`DISH_NOT_FOUND`, `ORDER_NOT_FOUND`), 409 (`EMAIL_TAKEN`,
`DISH_EXISTS`), 422 (`VALIDATION_ERROR` с `details`, `ORDER_TOO_SMALL`,
`NOT_ENOUGH_PORTIONS`, `DISH_UNAVAILABLE`, `INVALID_TRANSITION`, `CANNOT_CANCEL`),
500 (`DATABASE_ERROR`, без трассировки).

## Демонстрационный сценарий

Проверен на запущенной системе (`docker compose up`):

1. Регистрация клиента → вход → JWT.
2. Меню: первый запрос `X-Cache: MISS`, повторный — `HIT`.
3. Заказ «Стейк рибай + 2 морса» → 201, итог 2270 ₽ (доставка бесплатна), доставка `pending`.
4. Через секунду worker назначил курьера: `assigned`, «Алексей», ~40 мин.
5. Администратор: `cooking → ready → delivering (доставка on_the_way) → delivered`.
6. Ошибки: заказ на 190 ₽ → 422 `ORDER_TOO_SMALL`; пользователь добавляет блюдо → 403
   `ADMIN_ONLY`; чужой заказ → 403 `NOT_YOUR_ORDER`.
7. **Отказ Redis** (`docker compose stop redis`): меню отдаётся (200, `MISS`), `/health` →
   `redis: unavailable`.
8. **Отказ RabbitMQ** (`docker compose stop broker`): заказ создаётся, доставка `pending`,
   `outbox_backlog: 1`; после `docker compose start broker` relay отправил событие,
   курьер назначен, `outbox_backlog: 0`.
9. Данные сохраняются после `docker compose down` и повторного `up` (тома `db-data`,
   `broker-data`).

## Тесты

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest -v --cov --cov-report=term-missing           # SQLite + fakeredis
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost/test pytest   # PostgreSQL
```

39 тестов, покрытие **97 %**:

| Файл | Что проверяется |
|------|-----------------|
| `unit/test_security.py` | хеш пароля и соль, повреждённый хеш, JWT, просроченный и поддельный токен, правила пароля (параметризация) |
| `unit/test_order_service.py` | стоимость доставки (параметризация), создание заказа с outbox и инвалидацией кэша (Mock), бизнес-правила и откат, недоступное блюдо, отмена с возвратом порций, переходы статусов, чужой заказ, удаление |
| `unit/test_delivery_and_events.py` | балансировка курьеров и идемпотентность, синхронизация статусов, outbox relay, брокер недоступен (AsyncMock), кэш при отказе Redis |
| `integration/test_api.py` | регистрация и вход, 401/409/422, меню (фильтры, сортировка, поиск, кэш HIT/MISS), CRUD меню и права (401/403), полный цикл заказа, ошибки и доступ, отмена, health, вход администратора |
| `integration/test_broker.py` | событие через настоящий RabbitMQ (пропускается, если брокер не запущен) |

Из покрытия исключён `worker.py`: это бесконечные циклы фонового процесса; его логика
(`relay_once`, `consume`, обработчик) проверяется unit-тестами, тестом с настоящим
RabbitMQ и сценарием в Docker.

## Docker

`Dockerfile` двухэтапный (сборка колёс → slim-образ без компиляторов), запуск от
непривилегированного пользователя, `HEALTHCHECK` на `/health`. Один образ используется для
`app` и `worker`. `docker-compose.yml`: app, worker, PostgreSQL, Redis, RabbitMQ с
healthcheck, `depends_on: service_healthy`, томами и `restart: unless-stopped`.

```bash
docker build -t restaurant/app .
docker compose up --build -d && docker compose ps
docker compose logs -f app worker
```

## CI

`.github/workflows/lab21-ci.yml` (в корне репозитория), запускается при push и
pull request с изменениями `lab21_Burund/**`:

1. **test** — Python 3.12, установка зависимостей, `ruff check`, `ruff format --check`,
   pytest на PostgreSQL и RabbitMQ (сервисы GitHub Actions), `--cov-fail-under=85`;
2. **docker** (только после успешного test) — `docker compose build`, запуск системы,
   smoke-проверка `/health`, меню и ответа 401 без токена.

Пайплайн падает при ошибке линтера, тестов, недостаточном покрытии или неудачной сборке образа.

## Ограничения

- Оплата не реализована: заказ считается оплаченным при доставке.
- Курьеры — фиксированный список, ETA рассчитывается по формуле, а не по карте.
- Нет обновления JWT по refresh-токену и выхода из системы на сервере.
- Миграции схемы не используются: таблицы создаются при запуске (`create_all`).
- Worker запускается одним экземпляром; при нескольких экземплярах relay понадобится
  блокировка строк outbox (`SELECT … FOR UPDATE SKIP LOCKED`).
