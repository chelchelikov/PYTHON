"""Лабораторная работа №7. Вариант 5. Гостиница.

Версия 1 — РАБОЧАЯ, НО С НАМЕРЕННЫМИ НАРУШЕНИЯМИ SOLID.
Места нарушений отмечены комментариями «НАРУШЕНИЕ».
"""

from abc import ABC, abstractmethod
from datetime import date, datetime


class EmailSender:
    """Конкретная инфраструктурная зависимость."""

    def send(self, to, text):
        print(f"[EMAIL -> {to}] {text}")


# НАРУШЕНИЕ ISP: один «толстый» интерфейс на все случаи жизни.
# Клиенту, которому нужен только отчёт, приходится зависеть от бронирования,
# заселения, уведомлений и хранения.
class IHotelSystem(ABC):
    @abstractmethod
    def add_room(self, number, room_type, price, capacity): ...

    @abstractmethod
    def book(self, number, guest, email, check_in, check_out, guests): ...

    @abstractmethod
    def check_in(self, number): ...

    @abstractmethod
    def check_out(self, number): ...

    @abstractmethod
    def calculate_cost(self, room, nights, guests): ...

    @abstractmethod
    def notify(self, email, text): ...

    @abstractmethod
    def report(self): ...

    @abstractmethod
    def save_to_file(self, path): ...


class Room:
    def __init__(self, number, room_type, price, capacity):
        self.number = number
        self.room_type = room_type  # строка: "standard", "suite", "family"
        self.price = price
        self.capacity = capacity
        self.status = "free"

    def book(self):
        if self.status != "free":
            raise ValueError("Номер недоступен")
        self.status = "booked"


# НАРУШЕНИЕ LSP: наследник ломает контракт базового класса.
# Код, работающий с Room, ожидает, что свободный номер можно забронировать,
# а MaintenanceRoom бросает исключение.
class MaintenanceRoom(Room):
    def book(self):
        raise NotImplementedError("Номер на ремонте нельзя бронировать")


# НАРУШЕНИЕ SRP: класс хранит данные, бронирует, считает деньги,
# отправляет уведомления, строит отчёты, пишет в файл и общается с пользователем.
class HotelManager(IHotelSystem):
    def __init__(self):
        self.rooms = []
        self.bookings = []
        # НАРУШЕНИЕ DIP: сервис сам создаёт конкретную зависимость
        self.email_sender = EmailSender()

    def add_room(self, number, room_type, price, capacity):
        if room_type == "maintenance":
            room = MaintenanceRoom(number, room_type, price, capacity)
        else:
            room = Room(number, room_type, price, capacity)
        self.rooms.append(room)
        return room

    def find_room(self, number):
        for room in self.rooms:
            if room.number == number:
                return room
        return None

    # НАРУШЕНИЕ OCP: новый тип номера требует правки этого метода
    def calculate_cost(self, room, nights, guests):
        if room.room_type == "standard":
            return room.price * nights
        elif room.room_type == "suite":
            return (room.price + max(0, guests - 2) * 1500) * nights
        elif room.room_type == "family":
            return room.price * nights * (0.9 if guests >= 3 else 1)
        else:
            raise ValueError("Неизвестный тип номера")

    def book(self, number, guest, email, check_in, check_out, guests):
        room = self.find_room(number)
        if room is None:
            print("Номер не найден")  # НАРУШЕНИЕ SRP: бизнес-логика печатает в консоль
            return None
        room.book()
        nights = (check_out - check_in).days
        cost = self.calculate_cost(room, nights, guests)
        booking = {"room": number, "guest": guest, "email": email,
                   "check_in": check_in, "check_out": check_out, "cost": cost,
                   "status": "active"}
        self.bookings.append(booking)
        self.notify(email, f"Номер {number} забронирован, стоимость {cost} ₽")
        return booking

    def check_in(self, number):
        room = self.find_room(number)
        room.status = "occupied"
        print(f"Гость заселён в номер {number}")

    def check_out(self, number):
        room = self.find_room(number)
        room.status = "free"
        for booking in self.bookings:
            if booking["room"] == number and booking["status"] == "active":
                booking["status"] = "closed"
                self.notify(booking["email"], f"Спасибо! К оплате {booking['cost']} ₽")
                print(f"Гость выселен из номера {number}")

    def notify(self, email, text):
        self.email_sender.send(email, text)

    def report(self):
        print("===== ОТЧЁТ =====")
        for room in self.rooms:
            print(f"{room.number} {room.room_type} {room.status}")
        print("Выручка:", sum(b["cost"] for b in self.bookings))

    def save_to_file(self, path):
        with open(path, "w", encoding="utf-8") as file:
            for booking in self.bookings:
                file.write(str(booking) + "\n")


def main():
    manager = HotelManager()
    manager.add_room(101, "standard", 3500, 2)
    manager.add_room(201, "family", 5000, 4)
    manager.add_room(301, "suite", 9000, 4)
    manager.add_room(401, "maintenance", 3000, 2)
    while True:
        print("\n1. Бронирование  2. Заселение  3. Выселение  4. Отчёт  0. Выход")
        choice = input("> ").strip()
        if choice == "1":
            number = int(input("Номер: "))
            guest = input("Гость: ")
            email = input("E-mail: ")
            check_in = datetime.strptime(input("Заезд ДД.ММ.ГГГГ: "), "%d.%m.%Y").date()
            check_out = datetime.strptime(input("Выезд ДД.ММ.ГГГГ: "), "%d.%m.%Y").date()
            guests = int(input("Гостей: "))
            manager.book(number, guest, email, check_in, check_out, guests)
        elif choice == "2":
            manager.check_in(int(input("Номер: ")))
        elif choice == "3":
            manager.check_out(int(input("Номер: ")))
        elif choice == "4":
            manager.report()
        elif choice == "0":
            break


if __name__ == "__main__":
    main()
