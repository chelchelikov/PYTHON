"""Запуск из папки patterns:  python -m unittest discover -s tests -t . -v"""

import os
import tempfile
import unittest
from datetime import date

from factories.room_factory import RoomFactory
from factories.strategy_factory import StrategyFactory
from models.entities import HotelError
from models.enums import BookingStatus, RoomStatus, RoomType
from observers.observers import BookingLogger, BookingStatistics, GuestNotifier
from repositories.file_repository import FileRepository
from repositories.mappers import room_from_dict
from repositories.memory_repository import InMemoryRepository
from services.booking_service import BookingService
from strategies.regular import RegularTariff
from strategies.seasonal import SeasonalTariff
from strategies.weekend import WeekendTariff


def make_service(strategy=None):
    service = BookingService(InMemoryRepository(), InMemoryRepository(),
                             strategy or RegularTariff())
    service.add_room(RoomFactory.create("standard", 101))
    service.add_room(RoomFactory.create("suite", 301))
    return service


class FactoryTests(unittest.TestCase):
    def test_room_factory_creates_types(self):
        suite = RoomFactory.create(RoomType.SUITE, 301)
        family = RoomFactory.create("family", 201)
        self.assertEqual((suite.base_price, suite.capacity), (9000, 4))
        self.assertEqual(family.room_type, RoomType.FAMILY)
        with self.assertRaises(HotelError):
            RoomFactory.create("penthouse", 1)

    def test_strategy_factory(self):
        self.assertIsInstance(StrategyFactory.create("weekend"), WeekendTariff)
        with self.assertRaises(HotelError):
            StrategyFactory.create("vip")


class StrategyTests(unittest.TestCase):
    def test_strategy_changes_price(self):
        service = make_service()
        room = service.rooms()[0]
        # 18.12–22.12.2026: пт, сб, вс, пн; с 20.12 — высокий сезон
        check_in, check_out = date(2026, 12, 18), date(2026, 12, 22)
        regular = service.calculate_cost(room, check_in, check_out)
        service.set_strategy(SeasonalTariff())
        seasonal = service.calculate_cost(room, check_in, check_out)
        service.set_strategy(WeekendTariff())
        weekend = service.calculate_cost(room, check_in, check_out)
        self.assertEqual(regular, 3500 * 4)
        self.assertEqual(seasonal, 3500 * 2 + 3500 * 1.3 * 2)
        self.assertEqual(weekend, 3500 * 2 + 3500 * 1.2 * 2)


class RepositoryTests(unittest.TestCase):
    def test_memory_repository(self):
        repo = InMemoryRepository()
        repo.add(RoomFactory.create("standard", 1))
        self.assertEqual(repo.next_id(), 2)
        repo.delete(1)
        with self.assertRaises(HotelError):
            repo.get(1)

    def test_file_repository_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rooms.json")
            FileRepository(path, room_from_dict).add(RoomFactory.create("suite", 301))
            restored = FileRepository(path, room_from_dict).get(301)
            self.assertEqual(restored.room_type, RoomType.SUITE)
            self.assertEqual(restored.status, RoomStatus.FREE)


class BookingTests(unittest.TestCase):
    def test_book_and_cancel(self):
        service = make_service(WeekendTariff())
        booking = service.book(301, "Анна", date(2026, 11, 6), date(2026, 11, 8), 2)
        self.assertEqual(booking.cost, 9000 * 1.2 * 2)
        self.assertEqual(service.free_rooms(), [service.rooms()[0]])
        with self.assertRaises(HotelError):
            service.book(301, "Иван", date(2026, 11, 6), date(2026, 11, 8))
        service.cancel(booking.id)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertEqual(len(service.free_rooms()), 2)

    def test_invalid_booking(self):
        service = make_service()
        with self.assertRaises(HotelError):
            service.book(101, "Анна", date(2026, 11, 8), date(2026, 11, 6))
        with self.assertRaises(HotelError):
            service.book(101, "Анна", date(2026, 11, 6), date(2026, 11, 8), guests=5)


class ObserverTests(unittest.TestCase):
    def test_all_observers_receive_events(self):
        service = make_service()
        messages = []
        logger, statistics = BookingLogger(), BookingStatistics()
        for observer in (logger, GuestNotifier(messages.append), statistics):
            service.subscribe(observer)
        booking = service.book(101, "Иван", date(2026, 11, 2), date(2026, 11, 4))
        service.cancel(booking.id)
        self.assertEqual(len(logger.records), 2)
        self.assertEqual(len(messages), 2)
        self.assertEqual((statistics.created, statistics.cancelled, statistics.revenue),
                         (1, 1, 0))


if __name__ == "__main__":
    unittest.main()
