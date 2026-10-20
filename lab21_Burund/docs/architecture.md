# Архитектура итогового проекта «Ресторан с доставкой»

## Компоненты

```
            Client (браузер, Swagger, curl)
                      │ HTTP + JWT
                      ▼
┌──────────────────────────────────────────────┐
│ app (FastAPI)                                 │
│  api/  →  services/  →  repositories/  → ORM │──────► PostgreSQL (db)
│              │                                │        users, dishes, orders,
│              └─ cache.py ─────────────────────│──┐     order_items, deliveries,
└──────────────────────────────────────────────┘  │     outbox_events
                                                   ▼
                                                 Redis (кэш меню, TTL)
┌──────────────────────────────────────────────┐
│ worker (тот же образ, python -m app.worker)  │
│  outbox relay: outbox_events → RabbitMQ      │◄─────► PostgreSQL
│  consumer: order.* → DeliveryService.assign  │◄─────► RabbitMQ (exchange restaurant.events,
└──────────────────────────────────────────────┘          queue delivery.assignments)
```

## Слои приложения

| Слой | Папка | Ответственность |
|------|-------|-----------------|
| API | `src/app/api/` | HTTP: маршруты, коды ответов, зависимости (сессия, текущий пользователь, роль) |
| Схемы | `src/app/schemas/` | валидация входа и формат выхода (Pydantic) |
| Сервисы | `src/app/services/` | бизнес-правила, транзакции, outbox, инвалидация кэша |
| Репозитории | `src/app/repositories/` | запросы SQLAlchemy, без `commit` |
| Модели | `src/app/models/` | ORM-сущности и перечисления |
| Ядро | `src/app/core/` | настройки, ошибки, безопасность (PBKDF2, JWT), логирование |
| События | `src/app/events/`, `src/app/worker.py` | брокер, outbox relay, consumer |

## Модель данных

```
users 1───N orders 1───N order_items N───1 dishes
              │ 1
              └──1 deliveries
outbox_events — события, ожидающие отправки в брокер
```

| Таблица | Ключевые ограничения |
|---------|----------------------|
| users | email UNIQUE, role ∈ {user, admin} |
| dishes | name UNIQUE, price > 0, portions_available ≥ 0 |
| orders | FK user_id (RESTRICT), total ≥ 0, status — перечисление |
| order_items | FK order_id (CASCADE), FK dish_id (RESTRICT), quantity > 0, UNIQUE(order_id, dish_id) |
| deliveries | FK order_id UNIQUE (CASCADE) |
| outbox_events | published_at NULL — ещё не отправлено |

## Полный цикл заказа

```
POST /orders (USER)
  ├─ SELECT … FOR UPDATE блюд, проверка наличия и остатков, списание порций
  ├─ расчёт суммы, проверка минимальной суммы, стоимость доставки
  ├─ INSERT orders, order_items, deliveries(pending), outbox_events(order.created)
  └─ COMMIT (всё или ничего) → инвалидация кэша меню
worker: outbox → RabbitMQ → consumer → назначение курьера (assigned, ETA)
PATCH /orders/{id}/status (ADMIN): created → cooking → ready → delivering → delivered
PATCH /deliveries/{id} (ADMIN): on_the_way / delivered синхронизируют статус заказа
POST /orders/{id}/cancel: только created/cooking, порции возвращаются, доставка отменяется
```

## Отказоустойчивость

| Отказ | Поведение |
|-------|-----------|
| Redis недоступен | меню отдаётся из БД (`X-Cache: MISS`), `/health` → `redis: unavailable`, ошибок у клиента нет |
| RabbitMQ недоступен | заказы создаются; события остаются в `outbox_events` (`outbox_backlog` в `/health` растёт); после восстановления relay отправляет их, курьер назначается |
| worker остановлен | то же, что и при отказе брокера: события ждут в outbox |
| PostgreSQL недоступен | `/health` → 503, ошибки БД — 500 `DATABASE_ERROR` без трассировки |
