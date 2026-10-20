# Лабораторная работа №17. Вариант 5. Отель

Асинхронный Telegram-бот гостиницы на **aiogram 3**: поиск свободных номеров по датам,
пошаговое бронирование, отмена, изменение дат и история бронирований. Данные хранятся в
SQLite (**aiosqlite**) и сохраняются между перезапусками.

## Запуск

1. Создать бота у [@BotFather](https://t.me/BotFather) и получить токен.
2. Установить зависимости и задать переменные окружения:

```bash
pip install -r requirements.txt
cp .env.example .env          # BOT_TOKEN=..., ADMIN_IDS=ваш_telegram_id
python bot.py                 # при первом запуске БД заполняется (4 типа, 20 номеров)
pytest -v                     # 15 тестов, токен и сеть не нужны
```

Docker: `docker build -t hotel-bot . && docker run --env-file .env -v hotel-data:/data hotel-bot`.

Токен в коде не хранится: он читается из переменной `BOT_TOKEN` (файл `.env` в `.gitignore`).

## Возможности

| Команда / кнопка | Что делает |
|------------------|------------|
| `/start` | регистрация клиента и главное меню (Reply Keyboard из 5 пунктов) |
| `/help`, «❓ Помощь» | справка |
| `/search`, «🔎 Свободные номера» | FSM: заезд → выезд → гости → список свободных номеров (inline-кнопки) |
| `/book`, «🛎 Забронировать» | FSM из 6 состояний: заезд → выезд → гости → тип (inline) → номер (inline) → подтверждение |
| `/mybookings`, «📋 Мои бронирования» | история; по кнопке — карточка, «Изменить даты» (FSM), «Отменить бронь», «Удалить из истории» |
| `/types`, «🏨 Типы номеров» | типы номеров → номера типа → карточка номера |
| `/cancel`, «✖ Отмена» | прерывает любой сценарий FSM |
| `/admin`, `/stats`, `/users`, `/addroom`, `/toggle` | команды администратора (только для `ADMIN_IDS`) |

CRUD через Telegram: создание бронирования, просмотр (история и карточка), изменение дат,
отмена и удаление из истории; администратор добавляет номера и закрывает их для бронирования.

## Архитектура

```
Telegram → Dispatcher ─ middlewares (ServiceMiddleware, ActivityMiddleware)
              └─ routers: common, admin, rooms, booking, my_bookings, fallback   (handlers/)
                     │ клавиатуры (keyboards/), состояния FSM (states/)
                     ▼
              services/hotel.py, services/validation.py  — бизнес-правила
                     ▼
              database/repositories.py → database/db.py → SQLite
```

```
lab17_Burund/
├── bot.py                 # точка входа, create_dispatcher, обработчик ошибок
├── config.py              # переменные окружения
├── handlers/              # common, rooms, booking, my_bookings, admin, fallback, texts
├── keyboards/menu.py      # Reply- и Inline-клавиатуры, CallbackData
├── states/booking.py      # BookingForm, SearchForm, ChangeDatesForm
├── services/              # HotelService, валидация ввода
├── database/              # схема, демо-данные, репозитории
├── middlewares/           # внедрение сервиса, журнал активности
└── tests/                 # тесты сервиса и сквозные тесты через Dispatcher
```

Обработчики только принимают ввод и отвечают пользователю; правила (пересечение дат,
вместимость, чужие брони, отмена начавшейся брони) находятся в `HotelService`.

## База данных

```
room_types 1───N rooms 1───N bookings N───1 clients
activity — журнал действий пользователей (для статистики)
```

| Таблица | Поля |
|---------|------|
| `room_types` | id, name (unique), description |
| `rooms` | id, number (unique), type_id → room_types, floor, capacity, price, is_active |
| `clients` | id, telegram_id (unique), name, created_at |
| `bookings` | id, client_id → clients, room_id → rooms, check_in, check_out, guests, total, status, created_at; `CHECK (check_out > check_in)` |
| `activity` | id, telegram_id, action, created_at |

## Inline-кнопки и Callback Query

Используются фабрики `CallbackData` с идентификатором объекта: `type:pick:4`,
`room:pick:11`, `bk:cancel:7`, `confirm:yes`. Нажатие старой кнопки (например, уже отменённой
брони или кнопки из завершённого сценария) обрабатывается отдельно — бот отвечает
всплывающим сообщением.

## Валидация

Отдельно обрабатываются: неверный формат даты, дата в прошлом, выезд не позже заезда,
слишком длинный срок (> 30 ночей), количество гостей не числом или вне диапазона 1–6,
текст вместо нажатия кнопки, номер занят или вмещает меньше гостей, нечисловые аргументы
`/addroom`, неподдерживаемый тип сообщения (фото, стикер).

## Middleware

- `ServiceMiddleware` (outer) передаёт в обработчики `HotelService` — внедрение зависимости.
- `ActivityMiddleware` пишет в журнал `USER <id> <действие> (время мс)` и сохраняет действие
  в таблицу `activity`; по ней администратор видит число сообщений, пользователей и самое
  частое действие (`/stats`).

## Асинхронность

`asyncio` позволяет одному процессу обслуживать многих пользователей: пока обработчик ждёт
ответа Telegram или БД (`await`), event loop выполняет другие обработчики. `await`
приостанавливает корутину до готовности результата, не блокируя поток. Корутина
(`async def`) при вызове возвращает объект, который выполняет event loop, а обычная функция
выполняется сразу до конца. Блокирующие вызовы (`time.sleep`, синхронный `sqlite3`,
`requests`) внутри обработчика останавливают весь event loop, поэтому для БД используется
`aiosqlite`.

## Тесты

`tests/test_service.py` (8): заполнение БД, создание и получение брони, поиск свободных
номеров, двойное бронирование и вместимость, изменение дат, отмена и удаление, чужая бронь,
валидация, управление номерами.

`tests/test_bot.py` (7) — апдейты проходят через настоящий `Dispatcher` с фальшивой
HTTP-сессией (`FakeSession`), то есть проверяются роутеры, фильтры, FSM, клавиатуры и
middleware без сети: `/start`, полный FSM-сценарий бронирования с ошибками ввода, `/cancel`,
отмена через inline-кнопку, поиск, права администратора, журнал активности и устаревшая кнопка.
