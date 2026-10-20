"""Лабораторная работа №18. Вариант 5. Гостиница — консольный интерфейс.

Примеры (из папки lab18_Burund):
  python -m src.main add-room 101 standard 2 3500
  python -m src.main rooms
  python -m src.main free 2026-12-01 2026-12-05 --guests 2
  python -m src.main book 1 "Иванов Иван" 2026-12-01 2026-12-05 --guests 2
  python -m src.main cancel 1
  python -m src.main history "Иванов Иван"
"""

import argparse
import sys
from datetime import date

from src.exceptions import HotelError
from src.repositories import BookingRepository, RoomRepository, connect
from src.services import BookingService, RoomService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Система бронирования номеров")
    parser.add_argument("--db", default="hotel.db", help="файл SQLite")
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add-room", help="создать номер")
    add.add_argument("number")
    add.add_argument("room_type", choices=["standard", "deluxe", "suite", "family"])
    add.add_argument("capacity", type=int)
    add.add_argument("price", type=float)

    commands.add_parser("rooms", help="список номеров")

    free = commands.add_parser("free", help="свободные номера на период")
    free.add_argument("check_in", type=date.fromisoformat)
    free.add_argument("check_out", type=date.fromisoformat)
    free.add_argument("--guests", type=int, default=1)

    book = commands.add_parser("book", help="забронировать номер")
    book.add_argument("room_id", type=int)
    book.add_argument("guest")
    book.add_argument("check_in", type=date.fromisoformat)
    book.add_argument("check_out", type=date.fromisoformat)
    book.add_argument("--guests", type=int, default=1)

    cancel = commands.add_parser("cancel", help="отменить бронирование")
    cancel.add_argument("booking_id", type=int)

    history = commands.add_parser("history", help="бронирования гостя")
    history.add_argument("guest")
    return parser


def run(args: argparse.Namespace, out=None) -> int:
    out = out or sys.stdout
    connection = connect(args.db)
    rooms, bookings = RoomRepository(connection), BookingRepository(connection)
    room_service, booking_service = RoomService(rooms, bookings), BookingService(rooms, bookings)
    try:
        if args.command == "add-room":
            room = room_service.create_room(args.number, args.room_type, args.capacity, args.price)
            print(f"Создан номер {room.number} (id={room.id})", file=out)
        elif args.command == "rooms":
            for room in room_service.list_rooms():
                print(f"{room.id:>3}  №{room.number:<5} {room.room_type:<9} мест {room.capacity}  "
                      f"{room.price_per_night:.0f} ₽", file=out)
        elif args.command == "free":
            found = booking_service.find_free_rooms(args.check_in, args.check_out, args.guests)
            print(f"Свободно номеров: {len(found)}", file=out)
            for room in found:
                print(f"  №{room.number} ({room.room_type}, мест {room.capacity}) — "
                      f"{room.price_per_night:.0f} ₽/ночь", file=out)
        elif args.command == "book":
            booking = booking_service.book(args.room_id, args.guest, args.check_in,
                                           args.check_out, args.guests)
            print(f"Бронирование #{booking.id}: {booking.period.nights} ноч., "
                  f"{booking.total:.2f} ₽", file=out)
        elif args.command == "cancel":
            booking_service.cancel(args.booking_id)
            print(f"Бронирование #{args.booking_id} отменено", file=out)
        elif args.command == "history":
            for b in booking_service.guest_history(args.guest):
                print(f"#{b.id} номер id={b.room_id} {b.check_in} — {b.check_out} "
                      f"{b.total:.2f} ₽ [{b.status.value}]", file=out)
    except HotelError as error:
        print(f"Ошибка: {error}", file=out)
        return 1
    finally:
        connection.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
