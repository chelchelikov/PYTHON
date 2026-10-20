# Лабораторная работа №15. Вариант 5. Ресторан

Веб-приложение на **Flask**: меню ресторана (блюда и категории) и оформление заказов.
HTML-интерфейс (Jinja2) и REST API работают через общий слой сервисов, данные хранятся в
**PostgreSQL** (SQLAlchemy 2 ORM).

Сущности: **Dish** (блюдо), **Category** (категория), **Order** (заказ) и **OrderItem**
(позиция заказа: блюдо, количество, цена на момент заказа).

## Запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # строка подключения к PostgreSQL и SECRET_KEY
flask --app app seed              # создать таблицы и демонстрационные данные
flask --app app run               # http://127.0.0.1:5000
pytest -v                         # 15 тестов (SQLite в памяти)
TEST_DATABASE_URL=postgresql+psycopg://restaurant:restaurant@localhost/restaurant_web_test pytest -v
```

## Конфигурация

| Переменная | Назначение |
|------------|------------|
| `DATABASE_URL` | строка подключения SQLAlchemy к PostgreSQL |
| `SECRET_KEY` | ключ подписи сессии (нужен для flash-сообщений) |
| `FLASK_ENV` | окружение |
| `LOG_LEVEL` | уровень журнала |

Файл `.env` с реальными значениями в Git не добавляется (`.gitignore`).

## Архитектура

```
             Flask (Application Factory, app/__init__.py)
             ┌──────────────┴──────────────┐
   Blueprint web (HTML/Jinja2)     Blueprint api (/api, JSON)
             └──────────────┬──────────────┘
                 services/services.py   — бизнес-логика, валидация, ошибки
                            │
             repositories/repositories.py — запросы SQLAlchemy
                            │
                  models/models.py → PostgreSQL
```

- **Application Factory** `create_app(config)` — разные конфигурации для работы и тестов.
- **Blueprint** `web` и `api` разделяют HTML-маршруты и REST API.
- Сессия БД создаётся на каждый запрос (`flask.g`) и закрывается в `teardown_appcontext`.
- Сервисы не зависят от Flask и выбрасывают `ValidationError` (400), `NotFoundError` (404),
  `ConflictError` (409); обработчики ошибок превращают их в HTML-страницу или JSON.

```
app/
├── __init__.py            # create_app, обработчики ошибок, логирование, команда seed
├── config.py, database.py, seed.py
├── models/models.py       # Category, Dish, Order, OrderItem, OrderStatus
├── repositories/          # CategoryRepository, DishRepository, OrderRepository
├── services/              # CategoryService, DishService, OrderService
├── routes/web.py, api.py, forms.py
├── templates/             # base, index, dishes/*, categories/*, orders/*, 404, error
└── static/css, static/js
tests/                     # test_web.py, test_api.py, test_services.py
```

## База данных

| Таблица | Поля | Ограничения |
|---------|------|-------------|
| `categories` | id, name, description | `name` UNIQUE |
| `dishes` | id, name, description, price, weight_g, is_available, is_vegetarian, category_id | `name` UNIQUE, `price > 0`, `weight_g > 0`, FK → categories (RESTRICT) |
| `orders` | id, customer_name, table_number, status, comment, created_at | `table_number > 0`, статус — Enum |
| `order_items` | id, order_id, dish_id, quantity, price | FK → orders (CASCADE), FK → dishes (RESTRICT), `quantity > 0`, UNIQUE (order_id, dish_id) |

Связи: категория 1:N блюда, заказ 1:N позиции, блюдо 1:N позиции (заказы ↔ блюда — N:M).

## HTML-интерфейс

| Страница | Назначение |
|----------|------------|
| `/` | главная: категории, популярные блюда, последние заказы |
| `/dishes` | меню: поиск, фильтры (категория, цена до, вегетарианские, в наличии), сортировка (название, цена ↑↓, вес) |
| `/dishes/<id>` | карточка блюда, ссылка на категорию, кнопки «Заказать», «Изменить», «Удалить» |
| `/dishes/create`, `/dishes/<id>/edit` | формы создания и редактирования с сообщениями об ошибках |
| `/categories`, `/categories/<id>` | категории, блюда категории, добавление и удаление |
| `/orders` | заказы с фильтром по статусу и поиском по имени |
| `/orders/create` | оформление заказа: количество по каждому блюду, сумма считается на лету |
| `/orders/<id>` | состав заказа, смена статуса (новый → готовится → подан → оплачен, отмена) |

Для 404 и других ошибок есть собственные шаблоны `404.html` и `error.html`.

## REST API

| Метод | URL | Назначение | Коды |
|-------|-----|------------|------|
| GET | `/api/dishes?search=&category=&max_price=&vegetarian=1&available=1&sort=` | список блюд | 200 |
| GET | `/api/dishes/<id>` | блюдо | 200, 404 |
| POST | `/api/dishes` | создание | 201, 400, 409 |
| PUT | `/api/dishes/<id>` | полная замена | 200, 400, 404, 409 |
| PATCH | `/api/dishes/<id>` | частичное изменение | 200, 400, 404 |
| DELETE | `/api/dishes/<id>` | удаление | 204, 404, 409 |
| GET | `/api/categories` | категории | 200 |
| GET | `/api/categories/<id>/dishes` | блюда категории | 200, 404 |
| POST | `/api/categories` | новая категория | 201, 409 |
| GET | `/api/orders?status=&search=` | заказы | 200 |
| GET | `/api/orders/<id>` | заказ | 200, 404 |
| POST | `/api/orders` | оформить заказ | 201, 400, 404, 409 |
| PATCH | `/api/orders/<id>` | сменить статус | 200, 400, 409 |

```http
POST /api/orders
{"customer_name": "Бурунд", "table_number": 2,
 "items": [{"dish_id": 5, "quantity": 1}, {"dish_id": 9, "quantity": 2}]}

201 Created
{"id": 4, "customer_name": "Бурунд", "table_number": 2, "status": "new", "status_title": "новый",
 "total": 2650.0, "items": [{"dish_id": 5, "dish": "Стейк рибай", "quantity": 1, "price": 1890.0}, ...]}

PATCH /api/orders/4   {"status": "paid"}
409 {"error": "Заказ #4: нельзя перейти из «новый» в «оплачен»"}
```

## Логирование

В журнал пишутся запуск приложения, каждый HTTP-запрос (метод, путь, код, время),
создание, изменение и удаление блюд и категорий, оформление заказов и смена статуса,
а также внутренние ошибки с трассировкой (клиент её не видит).

## Тесты

15 тестов: открытие всех страниц, поиск, фильтры и сортировка, создание, изменение и удаление
через формы, ошибки форм, страница 404, оформление заказа и смена статуса, запрет удаления
блюда из заказа; CRUD через API, коды ошибок 400/404/409, API заказов, недоступное блюдо,
связанные сущности; частичное изменение, правила удаления категории, валидация заказа.
