"""Сквозные тесты: апдейты проходят через Dispatcher, роутеры, фильтры, FSM и middleware."""

import asyncio
from datetime import date, timedelta

from tests.helpers import ADMIN_ID, USER_ID, TelegramEmulator, make_service

TODAY = date.today()


def d(days: int) -> str:
    return (TODAY + timedelta(days=days)).strftime("%d.%m.%Y")


def run(scenario):
    async def wrapper():
        database, service = await make_service()
        try:
            await scenario(TelegramEmulator(service), service)
        finally:
            await database.close()
    asyncio.run(wrapper())


def test_start_and_help():
    async def scenario(tg, service):
        replies = await tg.send("/start")
        assert "Здравствуйте" in replies[0]
        assert "/search" in (await tg.send("❓ Помощь"))[0]
    run(scenario)


def test_booking_fsm_full_flow():
    async def scenario(tg, service):
        await tg.send("/book")
        assert "позже" in (await tg.send(d(3)) and await tg.send(d(2)))[0]  # выезд раньше заезда
        await tg.send(d(5))
        assert "числом" in (await tg.send("двое"))[0]
        assert "тип" in (await tg.send("2"))[0]
        assert "кнопками" in (await tg.send("люкс"))[0]  # ждём нажатия, а не текст
        lux = [data for text, data in tg.buttons() if text == "Люкс"][0]
        await tg.click(lux)
        room = tg.buttons()[0][1]
        assert "Итого" in (await tg.click(room))[0]
        replies = await tg.click("confirm:yes")
        assert "забронирован" in replies[0]
        history = await service.history(USER_ID)
        assert len(history) == 1 and history[0].room_type == "Люкс"
    run(scenario)


def test_cancel_command_stops_fsm():
    async def scenario(tg, service):
        await tg.send("/book")
        await tg.send(d(5))
        assert "отменена" in (await tg.send("/cancel"))[0]
        assert "Не понял" in (await tg.send(d(6)))[0]  # состояние сброшено
    run(scenario)


def test_my_bookings_cancel_via_inline():
    async def scenario(tg, service):
        booking = await service.book(USER_ID, "Тест", 1, TODAY + timedelta(days=4),
                                     TODAY + timedelta(days=6), 1)
        await tg.send("📋 Мои бронирования")
        assert tg.buttons()[0][1] == f"bk:show:{booking.id}"
        await tg.click(f"bk:show:{booking.id}")
        replies = await tg.click(f"bk:cancel:{booking.id}")
        assert "отменено" in replies[0]
        assert "не найдено" in (await tg.click(f"bk:cancel:{booking.id}", user_id=999))[0]
    run(scenario)


def test_search_flow():
    async def scenario(tg, service):
        await tg.send("🔎 Свободные номера")
        await tg.send(d(10))
        await tg.send(d(12))
        replies = await tg.send("5")
        assert "Свободно" in replies[0]
        assert {text.split()[0] for text, _ in tg.buttons()} == {"№205", "№404"}
    run(scenario)


def test_admin_rights():
    async def scenario(tg, service):
        assert "Неизвестная команда" in (await tg.send("/stats", user_id=USER_ID))[0]
        stats = (await tg.send("/stats", user_id=ADMIN_ID))[0]
        assert "Номеров: 20" in stats
        assert "Номер добавлен" in (await tg.send("/addroom 501 Люкс 5 4 15000",
                                                  user_id=ADMIN_ID))[0]
        assert "Формат" in (await tg.send("/addroom 502", user_id=ADMIN_ID))[0]
    run(scenario)


def test_middleware_logs_activity_and_stale_button():
    async def scenario(tg, service):
        await tg.send("/start")
        assert "устарела" in (await tg.click("unknown:data"))[0]
        stats = await service.activity.statistics()
        assert stats["messages"] == 2 and stats["users"] == 1
    run(scenario)
