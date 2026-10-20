import asyncio
from datetime import date, timedelta

import pytest

from services.hotel import BookingError
from services.validation import InputError, parse_check_out, parse_date, parse_guests
from tests.helpers import make_service

TODAY = date.today()
D = lambda days: TODAY + timedelta(days=days)  # noqa: E731


def run(coro):
    return asyncio.run(coro)


async def with_service(scenario):
    database, service = await make_service()
    try:
        return await scenario(service)
    finally:
        await database.close()


def test_seed_has_enough_records():
    async def scenario(service):
        return len(await service.room_types()), await service.rooms.count()
    types, rooms = run(with_service(scenario))
    assert types + rooms >= 20


def test_create_and_get_booking():
    async def scenario(service):
        booking = await service.book(1, "Анна", 1, D(5), D(8), 2)
        assert booking.total == 3200 * 3
        assert (await service.get_booking(1, booking.id)).room_number == "101"
        assert [b.id for b in await service.history(1)] == [booking.id]
    run(with_service(scenario))


def test_search_excludes_booked_and_respects_capacity():
    async def scenario(service):
        before = await service.search_free(D(5), D(8), 2)
        await service.book(1, "Анна", before[0].id, D(6), D(7), 1)
        after = await service.search_free(D(5), D(8), 2)
        assert len(after) == len(before) - 1
        big = await service.search_free(D(5), D(8), 5)
        assert {r.number for r in big} == {"205", "404"}
        lux = await service.search_free(D(5), D(8), 1, type_id=4)
        assert all(r.type_name == "Люкс" for r in lux)
    run(with_service(scenario))


def test_double_booking_and_capacity_errors():
    async def scenario(service):
        await service.book(1, "Анна", 1, D(5), D(8), 2)
        with pytest.raises(BookingError):
            await service.book(2, "Пётр", 1, D(7), D(9), 1)
        with pytest.raises(BookingError):
            await service.book(2, "Пётр", 3, D(10), D(12), 2)  # номер 103 на 1 гостя
    run(with_service(scenario))


def test_change_dates_and_cancel():
    async def scenario(service):
        booking = await service.book(1, "Анна", 11, D(5), D(7), 2)
        changed = await service.change_dates(1, booking.id, D(6), D(9))
        assert changed.total == 9000 * 3
        cancelled = await service.cancel(1, booking.id)
        assert cancelled.status == "cancelled"
        with pytest.raises(BookingError):
            await service.cancel(1, booking.id)
        await service.delete_cancelled(1, booking.id)
        assert await service.history(1) == []
    run(with_service(scenario))


def test_foreign_booking_is_hidden():
    async def scenario(service):
        booking = await service.book(1, "Анна", 1, D(5), D(8), 2)
        with pytest.raises(BookingError):
            await service.cancel(2, booking.id)
    run(with_service(scenario))


def test_validation():
    with pytest.raises(InputError, match="ДД.ММ.ГГГГ"):
        parse_date("завтра")
    with pytest.raises(InputError, match="прошлом"):
        parse_date((TODAY - timedelta(days=1)).strftime("%d.%m.%Y"))
    with pytest.raises(InputError, match="позже"):
        parse_check_out(D(3).strftime("%d.%m.%Y"), D(5))
    with pytest.raises(InputError, match="числом"):
        parse_guests("двое")
    with pytest.raises(InputError, match="от 1 до"):
        parse_guests("12")
    assert parse_guests(" 3 ") == 3


def test_admin_room_management():
    async def scenario(service):
        room = await service.add_room("501", "люкс", 5, 4, 15000)
        assert room.type_name == "Люкс"
        with pytest.raises(BookingError):
            await service.add_room("501", "Люкс", 5, 4, 15000)
        closed = await service.toggle_room("501")
        assert not closed.is_active
        with pytest.raises(BookingError):
            await service.book(1, "Анна", closed.id, D(5), D(6), 1)
    run(with_service(scenario))
