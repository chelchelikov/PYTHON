"""Тесты бизнес-логики. Не зависят от input()/print(): используется FakeNotifier.

Запуск из папки v2_refactored:  python -m unittest discover -s tests -t .
"""

import os
import tempfile
import unittest
from datetime import date

from models.entities import FamilyRoom, StandardRoom, SuiteRoom
from models.enums import BookingStatus, RoomStatus
from models.exceptions import BookingError, EntityNotFoundError, RoomUnavailableError
from repositories.json_repository import JsonFileRepository
from repositories.memory_repository import InMemoryRepository
from repositories.serializers import (booking_from_dict, booking_to_dict,
                                      room_from_dict, room_to_dict)
from services.booking_service import BookingService
from services.report_service import ReportService
from services.room_service import RoomService

CHECK_IN = date(2026, 12, 1)
CHECK_OUT = date(2026, 12, 4)


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def notify(self, recipient: str, message: str) -> None:
        self.messages.append((recipient, message))


def build(rooms=None, bookings=None):
    rooms = rooms if rooms is not None else InMemoryRepository()
    bookings = bookings if bookings is not None else InMemoryRepository()
    notifier = FakeNotifier()
    room_service = RoomService(rooms)
    for room in (StandardRoom(101, 1, 3500, 2), SuiteRoom(301, 3, 9000, 4),
                 FamilyRoom(201, 2, 5000, 4)):
        if not any(r.id == room.id for r in rooms.get_all()):
            room_service.add_room(room)
    return (room_service, BookingService(rooms, bookings, notifier),
            ReportService(rooms, bookings), notifier)


class BookingServiceTests(unittest.TestCase):
    def test_book_room_calculates_cost_and_notifies(self):
        rooms, service, _, notifier = build()
        booking = service.book(101, "Иванов", "ivanov@mail.ru", CHECK_IN, CHECK_OUT, 2)
        self.assertEqual(booking.cost, 3500 * 3)
        self.assertEqual(rooms.all_rooms()[0].status, RoomStatus.BOOKED)
        self.assertEqual(notifier.messages[0][0], "ivanov@mail.ru")

    def test_polymorphic_prices(self):
        _, service, _, _ = build()
        suite = service.book(301, "А", "a", CHECK_IN, CHECK_OUT, 4)
        family = service.book(201, "Б", "b", CHECK_IN, CHECK_OUT, 3)
        self.assertEqual(suite.cost, (9000 + 2 * 1500) * 3)
        self.assertEqual(family.cost, 5000 * 0.9 * 3)

    def test_cannot_book_unavailable_room(self):
        rooms, service, _, _ = build()
        rooms.set_maintenance(101, True)
        with self.assertRaises(RoomUnavailableError):
            service.book(101, "Иванов", "x", CHECK_IN, CHECK_OUT, 1)
        with self.assertRaises(RoomUnavailableError):
            service.book(301, "Иванов", "x", CHECK_IN, CHECK_OUT, 10)

    def test_invalid_dates(self):
        _, service, _, _ = build()
        with self.assertRaises(BookingError):
            service.book(101, "Иванов", "x", CHECK_OUT, CHECK_IN, 1)

    def test_full_cycle_check_in_check_out(self):
        rooms, service, reports, notifier = build()
        booking = service.book(301, "Петрова", "p", CHECK_IN, CHECK_OUT, 2)
        service.check_in(booking.id)
        self.assertEqual(reports.occupancy(), round(1 / 3 * 100, 1))
        service.check_out(booking.id)
        self.assertEqual(booking.status, BookingStatus.COMPLETED)
        self.assertTrue(all(r.status == RoomStatus.FREE for r in rooms.all_rooms()))
        self.assertEqual(len(notifier.messages), 3)
        with self.assertRaises(BookingError):
            service.check_out(booking.id)

    def test_cancel_excluded_from_revenue(self):
        _, service, reports, _ = build()
        first = service.book(101, "А", "a", CHECK_IN, CHECK_OUT, 1)
        service.book(301, "Б", "b", CHECK_IN, CHECK_OUT, 2)
        service.cancel(first.id)
        self.assertEqual(reports.revenue(), 9000 * 3)

    def test_unknown_booking(self):
        _, service, _, _ = build()
        with self.assertRaises(EntityNotFoundError):
            service.check_in(42)


class RepositorySubstitutionTests(unittest.TestCase):
    """LSP: сервис работает одинаково с памятью и с JSON-файлом."""

    def test_json_repository_persists_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            def repos():
                return (JsonFileRepository(os.path.join(tmp, "r.json"), room_to_dict, room_from_dict),
                        JsonFileRepository(os.path.join(tmp, "b.json"), booking_to_dict, booking_from_dict))

            rooms_repo, bookings_repo = repos()
            _, service, _, _ = build(rooms_repo, bookings_repo)
            service.book(301, "Сидоров", "s", CHECK_IN, CHECK_OUT, 3)

            rooms_repo, bookings_repo = repos()
            rooms, _, reports, _ = build(rooms_repo, bookings_repo)
            self.assertEqual(len(bookings_repo.get_all()), 1)
            self.assertIsInstance(rooms_repo.get(301), SuiteRoom)
            self.assertEqual(rooms_repo.get(301).status, RoomStatus.BOOKED)
            self.assertEqual(reports.revenue(), (9000 + 1500) * 3)


if __name__ == "__main__":
    unittest.main()
