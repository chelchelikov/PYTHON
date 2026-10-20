"""Лабораторная работа №8. Вариант 5. Гостиница — Repository, Factory, Strategy, Observer."""

import os

from factories.room_factory import RoomFactory
from factories.strategy_factory import StrategyFactory
from observers.observers import BookingLogger, BookingStatistics, GuestNotifier
from repositories.file_repository import FileRepository
from repositories.mappers import booking_from_dict, room_from_dict
from repositories.memory_repository import InMemoryRepository
from services.booking_service import BookingService
from ui.console import ConsoleUI

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def main() -> None:
    print("Выберите хранилище:\n1. Память\n2. Файл")
    if input("> ").strip() == "2":
        rooms = FileRepository(os.path.join(DATA_DIR, "rooms.json"), room_from_dict)
        bookings = FileRepository(os.path.join(DATA_DIR, "bookings.json"), booking_from_dict)
    else:
        rooms, bookings = InMemoryRepository(), InMemoryRepository()

    service = BookingService(rooms, bookings, StrategyFactory.create("regular"))
    logger, statistics = BookingLogger(), BookingStatistics()
    for observer in (logger, GuestNotifier(), statistics):
        service.subscribe(observer)

    if not service.rooms():
        for room_id, room_type in ((101, "standard"), (102, "standard"),
                                   (201, "family"), (301, "suite")):
            service.add_room(RoomFactory.create(room_type, room_id))

    ConsoleUI(service, logger, statistics).run()


if __name__ == "__main__":
    main()
