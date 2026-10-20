from datetime import date, datetime

from factories.room_factory import RoomFactory
from factories.strategy_factory import StrategyFactory
from models.entities import HotelError
from models.enums import RoomType
from observers.observers import BookingLogger, BookingStatistics
from services.booking_service import BookingService


class ConsoleUI:
    MENU = """
===== БРОНИРОВАНИЕ НОМЕРОВ =====
1. Показать номера
2. Свободные номера
3. Добавить номер (Factory)
4. Выбрать тариф (Strategy)
5. Рассчитать стоимость
6. Забронировать
7. Отменить бронь
8. Бронирования
9. Журнал и статистика (Observer)
0. Выход"""

    def __init__(self, service: BookingService, logger: BookingLogger,
                 statistics: BookingStatistics) -> None:
        self.service = service
        self.logger = logger
        self.statistics = statistics

    @staticmethod
    def read_int(prompt: str) -> int:
        while True:
            try:
                return int(input(prompt))
            except ValueError:
                print("Ошибка: введите целое число")

    @staticmethod
    def read_date(prompt: str) -> date:
        while True:
            try:
                return datetime.strptime(input(prompt).strip(), "%d.%m.%Y").date()
            except ValueError:
                print("Ошибка: формат ДД.ММ.ГГГГ")

    @staticmethod
    def print_rooms(rooms) -> None:
        for r in rooms:
            print(f"  {r.id:<5} {r.title:<18} мест {r.capacity}, {r.base_price:.0f} ₽, "
                  f"{', '.join(r.amenities)} — {r.status.value}")
        if not rooms:
            print("  нет номеров")

    def add_room(self) -> None:
        print("Типы:", ", ".join(t.value for t in RoomType))
        room = RoomFactory.create(input("Тип: ").strip(), self.read_int("Номер комнаты: "))
        self.service.add_room(room)
        print("Создан:", room.title, room.id)

    def choose_tariff(self) -> None:
        for name in StrategyFactory.names():
            print(f"  {name} — {StrategyFactory.create(name).title}")
        self.service.set_strategy(StrategyFactory.create(input("Тариф: ").strip()))
        print("Текущий тариф:", self.service.strategy.title)

    def calculate(self) -> None:
        room_id = self.read_int("Номер комнаты: ")
        room = next((r for r in self.service.rooms() if r.id == room_id), None)
        if room is None:
            raise HotelError("Номер не найден")
        check_in, check_out = self.read_date("Заезд: "), self.read_date("Выезд: ")
        for name in StrategyFactory.names():
            strategy = StrategyFactory.create(name)
            current = self.service.strategy
            self.service.set_strategy(strategy)
            cost = self.service.calculate_cost(room, check_in, check_out)
            self.service.set_strategy(current)
            print(f"  {strategy.title:<22} {cost:>10.2f} ₽")

    def book(self) -> None:
        booking = self.service.book(self.read_int("Номер комнаты: "), input("Гость: ").strip(),
                                    self.read_date("Заезд: "), self.read_date("Выезд: "),
                                    self.read_int("Гостей: "))
        print(f"Бронь #{booking.id} по тарифу {booking.tariff}: {booking.cost:.2f} ₽")

    def show_bookings(self) -> None:
        for b in self.service.bookings():
            print(f"  #{b.id} номер {b.room_id}, {b.guest}, {b.check_in:%d.%m}–"
                  f"{b.check_out:%d.%m.%Y}, {b.tariff}, {b.cost:.2f} ₽ — {b.status.value}")

    def show_observers(self) -> None:
        print("Журнал:")
        for record in self.logger.records:
            print("  ", record)
        s = self.statistics
        print(f"Статистика: создано {s.created}, отменено {s.cancelled}, "
              f"выручка {s.revenue:.2f} ₽, по тарифам {s.by_tariff}")

    def run(self) -> None:
        actions = {
            "1": lambda: self.print_rooms(self.service.rooms()),
            "2": lambda: self.print_rooms(self.service.free_rooms(self.read_int("Гостей: "))),
            "3": self.add_room, "4": self.choose_tariff, "5": self.calculate,
            "6": self.book, "7": lambda: self.service.cancel(self.read_int("Номер брони: ")),
            "8": self.show_bookings, "9": self.show_observers,
        }
        while True:
            print(self.MENU)
            print(f"(тариф: {self.service.strategy.title})")
            choice = input("Выберите действие: ").strip()
            if choice == "0":
                return
            action = actions.get(choice)
            if action is None:
                print("Неизвестный пункт меню")
                continue
            try:
                action()
            except HotelError as error:
                print("Ошибка:", error)
