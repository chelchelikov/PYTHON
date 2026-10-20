"""Пользовательский интерфейс: единственное место, где используются input() и print()."""

from datetime import date, datetime

from models.entities import FamilyRoom, StandardRoom, SuiteRoom
from models.exceptions import HotelError
from services.booking_service import BookingService
from services.report_service import ReportService
from services.room_service import RoomService

ROOM_TYPES = {"1": StandardRoom, "2": SuiteRoom, "3": FamilyRoom}


class ConsoleUI:
    MENU = """
===== ГОСТИНИЦА =====
1. Показать номера
2. Свободные номера
3. Добавить номер
4. Забронировать номер
5. Заселить по брони
6. Выселить по брони
7. Отменить бронь
8. Список бронирований
9. Номер на обслуживание / вернуть
10. Отчёт
0. Выход"""

    def __init__(self, rooms: RoomService, bookings: BookingService,
                 reports: ReportService) -> None:
        self._rooms = rooms
        self._bookings = bookings
        self._reports = reports
        self._actions = {
            "1": self.show_rooms, "2": self.show_free_rooms, "3": self.add_room,
            "4": self.book, "5": self.check_in, "6": self.check_out,
            "7": self.cancel, "8": self.show_bookings, "9": self.toggle_maintenance,
            "10": self.show_report,
        }

    @staticmethod
    def _read_int(prompt: str) -> int:
        while True:
            try:
                return int(input(prompt))
            except ValueError:
                print("Ошибка: введите целое число")

    @staticmethod
    def _read_float(prompt: str) -> float:
        while True:
            try:
                return float(input(prompt).replace(",", "."))
            except ValueError:
                print("Ошибка: введите число")

    @staticmethod
    def _read_date(prompt: str) -> date:
        while True:
            try:
                return datetime.strptime(input(prompt).strip(), "%d.%m.%Y").date()
            except ValueError:
                print("Ошибка: формат даты ДД.ММ.ГГГГ")

    @staticmethod
    def _print_rooms(rooms) -> None:
        if not rooms:
            print("Нет номеров")
        for room in rooms:
            print(f"  {room.id:<5} {room.kind:<9} этаж {room.floor}, мест {room.capacity}, "
                  f"{room.base_price:.0f} ₽/ночь — {room.status.value}")

    def show_rooms(self) -> None:
        self._print_rooms(self._rooms.all_rooms())

    def show_free_rooms(self) -> None:
        self._print_rooms(self._rooms.free_rooms(self._read_int("Количество гостей: ")))

    def add_room(self) -> None:
        cls = ROOM_TYPES.get(input("Тип (1 — стандарт, 2 — люкс, 3 — семейный): ").strip())
        if cls is None:
            print("Неизвестный тип номера")
            return
        room = cls(self._read_int("Номер комнаты: "), self._read_int("Этаж: "),
                   self._read_float("Цена за ночь: "), self._read_int("Вместимость: "))
        self._rooms.add_room(room)
        print("Номер добавлен")

    def book(self) -> None:
        booking = self._bookings.book(
            self._read_int("Номер комнаты: "), input("ФИО гостя: ").strip(),
            input("Контакт (e-mail/телефон): ").strip(),
            self._read_date("Заезд (ДД.ММ.ГГГГ): "), self._read_date("Выезд (ДД.ММ.ГГГГ): "),
            self._read_int("Количество гостей: "))
        print(f"Создана бронь #{booking.id}, стоимость {booking.cost:.2f} ₽")

    def check_in(self) -> None:
        self._bookings.check_in(self._read_int("Номер брони: "))
        print("Гость заселён")

    def check_out(self) -> None:
        booking = self._bookings.check_out(self._read_int("Номер брони: "))
        print(f"Гость выселен, к оплате {booking.cost:.2f} ₽")

    def cancel(self) -> None:
        self._bookings.cancel(self._read_int("Номер брони: "))
        print("Бронь отменена")

    def show_bookings(self) -> None:
        bookings = self._bookings.all_bookings()
        if not bookings:
            print("Бронирований нет")
        for b in bookings:
            print(f"  #{b.id} номер {b.room_id}: {b.guest_name}, "
                  f"{b.check_in:%d.%m.%Y}–{b.check_out:%d.%m.%Y}, {b.guests} гост., "
                  f"{b.cost:.2f} ₽ — {b.status.value}")

    def toggle_maintenance(self) -> None:
        room_id = self._read_int("Номер комнаты: ")
        enable = input("1 — отправить на обслуживание, 2 — вернуть: ").strip() == "1"
        room = self._rooms.set_maintenance(room_id, enable)
        print(f"Номер {room.id}: {room.status.value}")

    def show_report(self) -> None:
        print("===== ОТЧЁТ =====")
        for key, value in self._reports.summary().items():
            print(f"  {key}: {value}")

    def run(self) -> None:
        while True:
            print(self.MENU)
            choice = input("Выберите действие: ").strip()
            if choice == "0":
                print("До свидания!")
                return
            action = self._actions.get(choice)
            if action is None:
                print("Ошибка: неизвестный пункт меню")
                continue
            try:
                action()
            except (HotelError, ValueError) as error:
                print("Ошибка:", error)
