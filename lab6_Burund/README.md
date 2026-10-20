# Лабораторная работа №6. Вариант 5. Гостиница

Консольное приложение для управления номерами и бронированиями гостиницы.

## Запуск

```bash
python main.py
```

## Структура

| Файл | Назначение |
|------|------------|
| `main.py` | консольное меню и демонстрации |
| `models.py` | dataclass-модели `Entity`, `Room`, `StandardRoom`, `SuiteRoom`, `Guest`, `Booking`, Enum `RoomStatus` |
| `services.py` | бизнес-логика `HotelService`: бронирование, заселение, выселение, расчёт стоимости, статистика |
| `decorators.py` | `@log_call`, `@timed`, `@require_status(...)`, `@limit_calls(n)` |
| `context.py` | `HotelTransaction` (откат состояния при ошибке), `measure` (время выполнения блока) |
| `protocols.py` | Protocol `Reportable` и функция `print_report` |
| `introspection.py` | интроспекция объектов (`type`, `isinstance`, `issubclass`, `dir`, `hasattr`, `getattr`, `inspect`) |
| `exceptions.py` | `EntityNotFoundError`, `InvalidStatusError`, `BookingError` |

## Статусы номера

свободен → забронирован → занят → свободен; номер можно отправить на обслуживание.
Недопустимые переходы вызывают `InvalidStatusError`.

## Стоимость проживания

`цена за ночь × количество ночей`; в люксе каждый гость сверх двух оплачивается
дополнительно, VIP-гостям предоставляется скидка 10 %.
