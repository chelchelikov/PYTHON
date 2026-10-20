# Лабораторная работа №12. Вариант 5. Ресторан

Консольное приложение на **SQLAlchemy 2.x (ORM)** и **PostgreSQL**.
Сущности: `Customer`, `Dish`, `Order`, `OrderItem`. Основная операция —
создание заказа из нескольких блюд с расчётом стоимости (транзакция).

## Запуск

```bash
pip install -r requirements.txt
docker compose up -d            # PostgreSQL (или свой сервер, см. .env.example)
cp .env.example .env
python -m app.main              # при первом запуске ответить «д» — создать и заполнить БД
pytest -v                       # 13 тестов на SQLite в памяти
TEST_DATABASE_URL=postgresql+psycopg://restaurant:restaurant@localhost/restaurant_test pytest -v
```

## ER-диаграмма

```mermaid
erDiagram
    customers ||--o{ orders : "делает"
    orders ||--|{ order_items : "содержит"
    dishes ||--o{ order_items : "входит в"
    customers { int id PK; varchar name; varchar phone UK; varchar email UK; timestamp created_at }
    dishes { int id PK; varchar name UK; enum category; numeric price; int weight_g; int portions_left; bool is_available }
    orders { int id PK; int customer_id FK; int table_number; enum status; numeric total; timestamp created_at }
    order_items { int id PK; int order_id FK; int dish_id FK; int quantity; numeric price }
```

| Таблица | Назначение | Ограничения |
|---------|------------|-------------|
| `customers` | клиенты | `phone` UNIQUE NOT NULL, `email` UNIQUE |
| `dishes` | блюда меню | `name` UNIQUE, `price > 0`, `weight_g > 0`, `portions_left >= 0` |
| `orders` | заказы | FK `customer_id` (RESTRICT), `total >= 0`, статус — Enum |
| `order_items` | позиции заказа | FK `order_id` (CASCADE), FK `dish_id` (RESTRICT), `quantity > 0`, UNIQUE (`order_id`, `dish_id`) |

Связи: `Customer 1:N Order`, `Order 1:N OrderItem`, `Dish 1:N OrderItem`;
через `OrderItem` заказы и блюда связаны **многие-ко-многим** (позиция хранит количество и цену
на момент заказа).

## Структура

```
app/
├── database.py                  # Engine, sessionmaker, Base, init_db
├── models/entities.py           # ORM-модели и Enum
├── repositories/repositories.py # CRUD, поиск, фильтры, сортировка, агрегаты
├── services/services.py         # бизнес-логика, транзакции, обработка ошибок
├── seed.py                      # тестовые данные
├── exceptions.py
└── main.py                      # консольное меню
tests/                           # pytest
```

- **Repository** работает только с переданной `Session` и не вызывает `commit`.
- **Service** открывает сессию на каждую операцию (`BaseService.transaction`): `commit` при
  успехе, `rollback` при любой ошибке; ошибки `IntegrityError` переводятся в понятные
  `DuplicateError` / `ValidationError`.

## Реализованные запросы

| Операция | Метод |
|----------|-------|
| получение по ID | `BaseRepository.get_by_id` (`session.get`) |
| список | `get_all`, `DishRepository.find`, `OrderRepository.find` |
| фильтрация | блюда по категории, цене, наличию; заказы по статусу, сумме, дате, клиенту |
| несколько условий | `OrderRepository.find(status=..., min_total=..., created_after=...)` |
| сортировка | блюда по названию, цене, весу, остатку; заказы по дате или сумме |
| поиск | блюда по названию (`ILIKE`), клиенты по имени или телефону |
| связанные объекты | `CustomerRepository.get_with_orders` (заказы клиента с позициями, `selectinload`) |
| добавление / изменение / удаление | `create`, `update`, `delete` |
| агрегаты | `OrderRepository.statistics`: COUNT, SUM, AVG, MIN, MAX, топ блюд (GROUP BY) |

## Транзакции

`OrderService.create_order(customer_id, table, {dish_id: количество})`:

1. проверить, что клиент существует;
2. загрузить блюда с блокировкой строк (`SELECT … FOR UPDATE`);
3. для каждого блюда проверить доступность и остаток порций, уменьшить остаток;
4. создать заказ и позиции (цена фиксируется на момент заказа);
5. посчитать сумму и выполнить `COMMIT`.

Если, например, одного блюда не хватает, выполняется `ROLLBACK`: остатки остальных блюд не
меняются, заказ не создаётся (тест `test_order_rollback_when_not_enough_portions`).

`OrderService.cancel_order` — вторая транзакция: статус «отменён» и возврат порций.

## Обработка ошибок

| Ситуация | Исключение |
|----------|------------|
| объект не найден | `NotFoundError` |
| дубликат (телефон, e-mail, название блюда) | `DuplicateError` |
| нарушение внешнего ключа (удаление клиента с заказами) | `ValidationError` |
| не хватает порций, недопустимый статус | `OrderError` (транзакция отменена) |
| некорректные данные (цена ≤ 0, пустое имя) | `ValidationError` |

Консольное приложение перехватывает `RestaurantError` и продолжает работу.

## Тесты

13 тестов (`tests/test_restaurant.py`): CRUD, дубликаты и валидация, фильтры и сортировка,
поиск, связанные объекты, внешний ключ, транзакция и её откат, отмена заказа,
запрос с несколькими условиями, агрегаты. Проверены на SQLite и PostgreSQL 16.
