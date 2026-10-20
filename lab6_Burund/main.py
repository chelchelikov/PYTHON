"""Лабораторная работа №6. Вариант 5. Гостиница."""

from datetime import date, datetime

import decorators
from context import HotelTransaction, measure
from decorators import limit_calls
from exceptions import HotelError
from introspection import inspect_object, is_subclass_report
from models import Entity, Guest, Room, RoomStatus, StandardRoom, SuiteRoom
from protocols import Reportable, print_report
from services import HotelService


def read_int(prompt: str) -> int:
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            print("Ошибка: необходимо ввести целое число")


def read_float(prompt: str) -> float:
    while True:
        try:
            return float(input(prompt).replace(",", "."))
        except ValueError:
            print("Ошибка: необходимо ввести число")


def read_date(prompt: str) -> date:
    while True:
        try:
            return datetime.strptime(input(prompt).strip(), "%d.%m.%Y").date()
        except ValueError:
            print("Ошибка: дата вводится в формате ДД.ММ.ГГГГ")


def read_status() -> RoomStatus:
    statuses = list(RoomStatus)
    for index, status in enumerate(statuses, 1):
        print(f"  {index}. {status.value}")
    while True:
        index = read_int("Новый статус: ")
        if 1 <= index <= len(statuses):
            return statuses[index - 1]
        print("Ошибка: нет такого статуса")


def create_hotel() -> HotelService:
    decorators.LOG_ENABLED = False
    hotel = HotelService("Северная звезда")
    hotel.add_room(StandardRoom(1, "101", 1, 3500, 2, has_window_view=True))
    hotel.add_room(StandardRoom(2, "102", 1, 3200, 2))
    hotel.add_room(StandardRoom(3, "201", 2, 4000, 3, has_window_view=True))
    hotel.add_room(SuiteRoom(4, "301", 3, 9000, 4, rooms_count=3))
    hotel.add_room(SuiteRoom(5, "302", 3, 8500, 3))
    hotel.add_guest(Guest(1, "Иванов Иван", "+7 900 111-22-33"))
    hotel.add_guest(Guest(2, "Петрова Анна", "+7 900 444-55-66", is_vip=True))
    hotel.book_room(4, 2, date(2026, 11, 1), date(2026, 11, 5), 3)
    hotel.check_in(4)
    decorators.LOG_ENABLED = True
    return hotel


def add_room(hotel: HotelService) -> None:
    kind = input("Тип номера (1 — стандарт, 2 — люкс): ").strip()
    room_id = max((r.id for r in hotel.rooms), default=0) + 1
    name = input("Номер комнаты: ").strip()
    floor = read_int("Этаж: ")
    price = read_float("Цена за ночь: ")
    capacity = read_int("Вместимость: ")
    room_class = SuiteRoom if kind == "2" else StandardRoom
    hotel.add_room(room_class(room_id, name, floor, price, capacity))


def find_room(hotel: HotelService) -> None:
    room = hotel.find_room_by_name(input("Номер комнаты: ").strip())
    print(room.get_report_data() if room else "Номер не найден")


def show_all(hotel: HotelService) -> None:
    print(f"Номера гостиницы «{hotel.name}»:")
    print_report(hotel.rooms)
    print("Гости:")
    print_report(hotel.guests)
    print("Бронирования:")
    print_report(hotel.bookings)


def change_status(hotel: HotelService) -> None:
    room = hotel.change_room_status(read_int("id номера: "), read_status())
    print(room.get_report_data())


def domain_operation(hotel: HotelService) -> None:
    print("  1. Забронировать номер\n  2. Заселить\n  3. Выселить и рассчитать\n"
          "  4. Свободные номера\n  5. Рассчитать стоимость проживания")
    choice = input("Операция: ").strip()
    if choice == "1":
        booking = hotel.book_room(read_int("id номера: "), read_int("id гостя: "),
                                  read_date("Заезд (ДД.ММ.ГГГГ): "),
                                  read_date("Выезд (ДД.ММ.ГГГГ): "),
                                  read_int("Количество гостей: "))
        print(booking.get_report_data())
        print(f"Стоимость: {hotel.booking_cost(booking):.2f} ₽")
    elif choice == "2":
        print(hotel.check_in(read_int("id номера: ")).get_report_data())
    elif choice == "3":
        print(f"К оплате: {hotel.check_out(read_int('id номера: ')):.2f} ₽")
    elif choice == "4":
        print_report(hotel.free_rooms(read_int("Количество гостей: ")))
    elif choice == "5":
        room = hotel.get_room(read_int("id номера: "))
        guest = hotel.get_guest(read_int("id гостя: "))
        cost = hotel.calculate_cost(room, guest, read_date("Заезд: "), read_date("Выезд: "),
                                    read_int("Количество гостей: "))
        print(f"Стоимость проживания: {cost:.2f} ₽")
    else:
        print("Неизвестная операция")


def show_statistics(hotel: HotelService) -> None:
    for key, value in hotel.statistics().items():
        print(f"  {key}: {value}")


def introspect(hotel: HotelService) -> None:
    print("  1. Номер\n  2. Гость\n  3. Бронирование")
    choice = input("Объект: ").strip()
    if choice == "2":
        obj = hotel.get_guest(read_int("id гостя: "))
    elif choice == "3":
        index = read_int("id брони: ")
        obj = next((b for b in hotel.bookings if b.id == index), None)
        if obj is None:
            print("Бронирование не найдено")
            return
    else:
        obj = hotel.get_room(read_int("id номера: "))
    inspect_object(obj)
    print(is_subclass_report(type(obj), Entity))
    print("isinstance(obj, Room):", isinstance(obj, Room))


@limit_calls(2)
def greet_guest(name: str) -> str:
    return f"Добро пожаловать, {name}!"


def demo_decorators(hotel: HotelService) -> None:
    print("1) @log_call + @require_status(FREE) — бронирование занятого номера:")
    try:
        hotel.book_room(4, 1, date(2026, 12, 1), date(2026, 12, 3))
    except HotelError as error:
        print("   Ошибка:", error)
    print("2) @timed — расчёт статистики:")
    hotel.statistics()
    print("3) @limit_calls(2) — третий вызов запрещён:")
    for name in ("Иван", "Анна", "Олег"):
        try:
            print("  ", greet_guest(name))
        except RuntimeError as error:
            print("   Ошибка:", error)
    print("Имя функции сохранено благодаря @wraps:", greet_guest.__name__)


def demo_context(hotel: HotelService) -> None:
    free = hotel.free_rooms()
    if not free:
        print("Нет свободных номеров для демонстрации")
        return
    room = free[0]
    busy = next((r for r in hotel.rooms if r.status != RoomStatus.FREE), None)
    with measure("пакетное бронирование"):
        try:
            with HotelTransaction(hotel, f"бронирование номеров {room.name} и "
                                         f"{busy.name if busy else '—'}"):
                hotel.book_room(room.id, 1, date(2026, 12, 10), date(2026, 12, 12))
                print(f"Номер {room.name} внутри транзакции:", hotel.get_room(room.id).status.value)
                if busy is None:
                    raise HotelError("свободных номеров больше нет")
                hotel.book_room(busy.id, 1, date(2026, 12, 10), date(2026, 12, 12))
        except HotelError:
            pass
    print(f"Номер {room.name} после отката:", hotel.get_room(room.id).status.value)


def demo_protocol(hotel: HotelService) -> None:
    items: list[Reportable] = [hotel.rooms[0], hotel.guests[1], *hotel.bookings[:1]]
    print("Объекты разных классов через Protocol Reportable:")
    print_report(items)


def demo_dataclass_enum(hotel: HotelService) -> None:
    room = StandardRoom(99, "999", 9, 3000, 2)
    print("dataclass:", room)
    print("Сравнение dataclass по полям:", room == StandardRoom(99, "999", 9, 3000, 2))
    room.change_status(RoomStatus.MAINTENANCE)
    print("Enum: статус", room.status, "→", room.status.value)
    try:
        room.change_status(RoomStatus.OCCUPIED)
    except HotelError as error:
        print("Недопустимый переход:", error)


MENU = """
===== ГОСТИНИЦА =====
1. Добавить номер
2. Удалить номер
3. Найти номер
4. Вывести все объекты
5. Изменить состояние номера
6. Операции предметной области
7. Статистика
8. Интроспекция объекта
9. Демонстрация декораторов
10. Демонстрация контекстного менеджера
11. Демонстрация Protocol, dataclass и Enum
0. Выход"""


def main() -> None:
    hotel = create_hotel()
    actions = {
        "1": add_room,
        "2": lambda h: print("Удалён:", h.remove_room(read_int("id номера: ")).name),
        "3": find_room,
        "4": show_all,
        "5": change_status,
        "6": domain_operation,
        "7": show_statistics,
        "8": introspect,
        "9": demo_decorators,
        "10": demo_context,
        "11": lambda h: (demo_protocol(h), demo_dataclass_enum(h)),
    }
    while True:
        print(MENU)
        choice = input("Выберите действие: ").strip()
        if choice == "0":
            print("До свидания!")
            break
        action = actions.get(choice)
        if action is None:
            print("Ошибка: неизвестный пункт меню")
            continue
        try:
            action(hotel)
        except HotelError as error:
            print("Ошибка:", error)
        except (ValueError, ZeroDivisionError) as error:
            print("Ошибка:", error)


if __name__ == "__main__":
    main()
