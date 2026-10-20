# Лабораторная работа №18. Вариант 5. Гостиница

Система бронирования номеров (консольное приложение) и набор автоматических тестов на
**pytest** с **unittest.mock**.

## Запуск

```bash
pip install -r requirements.txt
pytest                                          # все тесты
pytest --cov=src --cov-report=term-missing      # с покрытием
pytest -m integration                           # только интеграционные

python -m src.main add-room 101 standard 2 3500
python -m src.main free 2026-12-01 2026-12-05 --guests 2
python -m src.main book 1 "Иванов Иван" 2026-12-01 2026-12-05 --guests 2
python -m src.main cancel 1
```

## Архитектура

```
src/main.py (CLI, argparse)
    ↓
src/services/  RoomService, BookingService   — бизнес-правила
    ↓
src/repositories/sqlite.py  RoomRepository, BookingRepository
    ↓
SQLite
```

| Класс | Назначение |
|-------|------------|
| `Room`, `Booking` | модели (dataclass) |
| `DateRange` | период `[заезд, выезд)`: `nights`, `overlaps()` — день выезда не занят |
| `RoomService` | создание номера с проверками, получение, смена цены, удаление (нельзя при активных бронях) |
| `BookingService` | бронирование (проверка периода, вместимости, пересечений), расчёт стоимости (скидка 10 % от 7 ночей), отмена, поиск свободных номеров, история гостя |
| `NotFoundError`, `ValidationError`, `BookingConflictError`, `OperationNotAllowedError` | ошибочные ситуации |

`BookingService` получает функцию «текущей даты» (`today`) через конструктор, поэтому тесты не
зависят от дня запуска.

## Стратегия тестирования

```
tests/
├── conftest.py                    # фикстуры: Mock-репозитории, сервисы, БД SQLite в памяти
├── unit/
│   ├── test_models.py             # DateRange: пересечение периодов, число ночей
│   ├── test_room_service.py       # RoomService с Mock-репозиториями
│   └── test_booking_service.py    # BookingService с Mock-репозиториями и patch
└── integration/
    └── test_sqlite.py             # Service + Repository + SQLite, CLI целиком
```

| Вид | Количество | Примеры |
|-----|-----------:|---------|
| unit-тесты (функции) | 20 | создание номера, бронирование, отмена, поиск свободных, расчёт стоимости |
| с Mock / patch | 14 | `room_repo.add.call_args`, `assert_called_once_with(1)`, `assert_not_called()`, `side_effect`, `patch("src.services.booking_service.date")` |
| параметризованные | 7 (39 наборов данных) | пересечение периодов, число ночей, валидация номера, граничные значения, ошибки бронирования, скидка, запрещённая отмена |
| интеграционные | 3 | полный цикл бронирования, удаление номера с бронями, CLI end-to-end |

Всего 23 тестовые функции, pytest выполняет **52 теста** (с учётом параметров).

Проверены:

- **положительные сценарии** — создание номера, бронирование, отмена, поиск свободных
  номеров, смена цены, удаление;
- **отрицательные** — номер не найден, некорректный id (`0`), дубликат номера, пересечение
  периодов, повторная отмена, отмена начавшейся брони, удаление номера с активными бронями;
- **граничные значения** — 0 и 1 ночь, 30 и 31 ночь, 0 гостей и больше вместимости,
  вместимость 0 / 1 / 6 / 7, цена 0 / 0,01 / максимум / сверх максимума, пустая строка и
  строка из пробелов, пустой список номеров, заезд в день выезда предыдущего гостя
  (разрешено), 6 и 7 ночей (скидка).

Пример Mock-теста:

```python
def test_book_overlapping_period_raises_conflict(booking_service, booking_repo):
    booking_repo.active_for_room.return_value = [existing(10, 15)]
    with pytest.raises(BookingConflictError):
        booking_service.book(1, "Иванов", D(12), D(14), 1)
    booking_repo.add.assert_not_called()
```

## Покрытие

```
Name                              Stmts   Miss  Cover
src/exceptions.py                     8      0   100%
src/main.py                          66     13    80%
src/models/entities.py               38      0   100%
src/repositories/sqlite.py           60      3    95%
src/services/booking_service.py      60      0   100%
src/services/room_service.py         42      1    98%
TOTAL                               281     17    94%
```

Сервисный слой покрыт на 98–100 %. Даже при 100 % покрытии остаются непроверенными,
например, одновременное бронирование одного номера из двух процессов (гонка между проверкой
и вставкой), даты на границе года и високосный день, очень длинные имена гостей,
поведение при повреждённом файле БД.

## Обнаруженная ошибка

Интеграционный тест `test_room_with_bookings_cannot_be_deleted` упал с
`sqlite3.IntegrityError: FOREIGN KEY constraint failed`: после отмены всех броней номер всё
равно нельзя было удалить, потому что в таблице `bookings` оставались отменённые записи,
ссылающиеся на него. Unit-тесты эту ошибку не нашли: Mock-репозиторий не знает о внешних
ключах. Исправление — `ON DELETE CASCADE` для `bookings.room_id`; активные брони по-прежнему
блокируют удаление на уровне `RoomService`. Это пример того, зачем нужны интеграционные
тесты в дополнение к unit-тестам.
