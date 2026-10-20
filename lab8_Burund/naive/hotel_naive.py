"""Лабораторная работа №8. Вариант 5. Гостиница — наивная реализация (этап 1).

Без паттернов: создание номеров, выбор тарифа и уведомления — через if/elif
и жёсткие вызовы, данные хранятся прямо в сервисе.
"""

from datetime import date, timedelta


class HotelService:
    def __init__(self):
        self.rooms = {}       # хранение внутри сервиса
        self.bookings = []
        self.log = []
        self.revenue = 0.0

    def create_room(self, number, room_type):
        # Создание объектов через if/elif: новый тип номера = правка метода
        if room_type == "standard":
            room = {"number": number, "type": "standard", "price": 3500, "capacity": 2}
        elif room_type == "suite":
            room = {"number": number, "type": "suite", "price": 9000, "capacity": 4}
        elif room_type == "family":
            room = {"number": number, "type": "family", "price": 5500, "capacity": 5}
        else:
            raise ValueError("Неизвестный тип номера")
        room["status"] = "free"
        self.rooms[number] = room
        return room

    def calculate_cost(self, room, check_in, check_out, tariff):
        total = 0.0
        day = check_in
        while day < check_out:
            # Выбор алгоритма через if/elif: новый тариф = правка метода
            if tariff == "regular":
                total += room["price"]
            elif tariff == "seasonal":
                high = day.month in (6, 7, 8) or (day.month == 12 and day.day >= 20)
                total += room["price"] * (1.3 if high else 1.0)
            elif tariff == "weekend":
                total += room["price"] * (1.2 if day.weekday() in (4, 5) else 1.0)
            else:
                raise ValueError("Неизвестный тариф")
            day += timedelta(days=1)
        return round(total, 2)

    def book(self, number, guest, check_in, check_out, tariff):
        room = self.rooms[number]
        if room["status"] != "free":
            raise ValueError("Номер занят")
        cost = self.calculate_cost(room, check_in, check_out, tariff)
        room["status"] = "booked"
        booking = {"room": number, "guest": guest, "cost": cost}
        self.bookings.append(booking)
        # Жёсткие вызовы уведомлений: добавить SMS = правка метода
        self.log.append(f"Бронь номера {number} для {guest}")
        print(f"[ГОСТЮ {guest}] Номер {number} забронирован, {cost} ₽")
        self.revenue += cost
        return booking


if __name__ == "__main__":
    service = HotelService()
    service.create_room(101, "standard")
    service.create_room(301, "suite")
    service.book(301, "Анна", date(2026, 12, 18), date(2026, 12, 22), "seasonal")
    service.book(101, "Иван", date(2026, 11, 6), date(2026, 11, 9), "weekend")
    print("Журнал:", service.log)
    print("Выручка:", service.revenue)
