"""Лабораторная работа №7. Вариант 5. Гостиница — версия после рефакторинга по SOLID.

main.py — «корень композиции»: здесь создаются конкретные реализации
и передаются в сервисы через конструкторы (Dependency Injection).
"""

import os

from infrastructure.notifier import CompositeNotifier, ConsoleNotifier, FileNotifier
from models.entities import FamilyRoom, StandardRoom, SuiteRoom
from repositories.json_repository import JsonFileRepository
from repositories.memory_repository import InMemoryRepository
from repositories.serializers import (booking_from_dict, booking_to_dict,
                                      room_from_dict, room_to_dict)
from services.booking_service import BookingService
from services.report_service import ReportService
from services.room_service import RoomService
from ui.console import ConsoleUI

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def create_repositories(choice: str):
    if choice == "2":
        rooms = JsonFileRepository(os.path.join(DATA_DIR, "rooms.json"),
                                   room_to_dict, room_from_dict)
        bookings = JsonFileRepository(os.path.join(DATA_DIR, "bookings.json"),
                                      booking_to_dict, booking_from_dict)
    else:
        rooms = InMemoryRepository()
        bookings = InMemoryRepository()
    return rooms, bookings


def seed_rooms(room_service: RoomService) -> None:
    if room_service.all_rooms():
        return
    for room in (StandardRoom(101, 1, 3500, 2), StandardRoom(102, 1, 3200, 2),
                 FamilyRoom(201, 2, 5000, 4), SuiteRoom(301, 3, 9000, 4),
                 SuiteRoom(302, 3, 8500, 3)):
        room_service.add_room(room)


def main() -> None:
    print("Выберите хранилище:\n1. Память\n2. Файл (JSON)")
    rooms, bookings = create_repositories(input("> ").strip())

    print("Уведомления:\n1. Консоль\n2. Консоль + журнал в файле")
    notifier = ConsoleNotifier()
    if input("> ").strip() == "2":
        os.makedirs(DATA_DIR, exist_ok=True)
        notifier = CompositeNotifier(notifier, FileNotifier(os.path.join(DATA_DIR, "notify.log")))

    room_service = RoomService(rooms)
    booking_service = BookingService(rooms, bookings, notifier)
    report_service = ReportService(rooms, bookings)
    seed_rooms(room_service)

    ConsoleUI(room_service, booking_service, report_service).run()


if __name__ == "__main__":
    main()
