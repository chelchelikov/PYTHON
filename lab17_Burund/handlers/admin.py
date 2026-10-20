from aiogram import Router
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import Message

from config import Config
from handlers.texts import room_card
from services.hotel import BookingError, HotelService
from services.validation import InputError


class IsAdmin(BaseFilter):
    async def __call__(self, message: Message, config: Config) -> bool:
        return message.from_user is not None and message.from_user.id in config.admin_ids


ROUTER_NAME = "admin"

ADMIN_HELP = ("<b>Команды администратора</b>\n"
              "/stats — статистика\n/users — клиенты\n"
              "/addroom номер тип этаж мест цена — добавить номер\n"
              "   пример: /addroom 501 Люкс 5 4 15000\n"
              "/toggle номер — закрыть/открыть номер для бронирования")


async def admin_help(message: Message) -> None:
    await message.answer(ADMIN_HELP)


async def stats(message: Message, service: HotelService) -> None:
    s = await service.statistics()
    await message.answer(
        f"<b>Статистика</b>\nНомеров: {s['rooms']}\nКлиентов: {s['clients']}\n"
        f"Бронирований: {s['total']} (активных {s['active']})\n"
        f"Выручка по активным: {s['revenue']:.0f} ₽\nПопулярный тип: {s['popular_type']}\n"
        f"Сообщений и нажатий: {s['messages']} от {s['users']} пользователей\n"
        f"Самое частое действие: {s['popular_action']}")


async def users(message: Message, service: HotelService) -> None:
    rows = await service.clients.all()
    lines = [f"{c.id}. {c.name} (id {c.telegram_id}) — броней: {n}" for c, n in rows]
    await message.answer("<b>Клиенты</b>\n" + ("\n".join(lines) or "пока нет"))


async def add_room(message: Message, command: CommandObject, service: HotelService) -> None:
    parts = (command.args or "").split()
    if len(parts) != 5:
        await message.answer("Формат: /addroom номер тип этаж мест цена")
        return
    number, type_name, floor, capacity, price = parts
    try:
        floor_value, capacity_value, price_value = int(floor), int(capacity), float(price)
        room = await service.add_room(number, type_name, floor_value, capacity_value, price_value)
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return
    except ValueError:  # int()/float() не смогли разобрать аргументы
        await message.answer("⚠️ Этаж, количество мест и цена должны быть числами")
        return
    except BookingError as error:
        await message.answer(f"⚠️ {error}")
        return
    await message.answer("Номер добавлен:\n" + room_card(room))


async def toggle_room(message: Message, command: CommandObject, service: HotelService) -> None:
    if not command.args:
        await message.answer("Формат: /toggle номер")
        return
    try:
        room = await service.toggle_room(command.args.strip())
    except BookingError as error:
        await message.answer(f"⚠️ {error}")
        return
    await message.answer(room_card(room))


def create_router() -> Router:
    router = Router(name=ROUTER_NAME)
    router.message.filter(IsAdmin())
    router.message.register(admin_help, Command("admin"))
    router.message.register(stats, Command("stats"))
    router.message.register(users, Command("users"))
    router.message.register(add_room, Command("addroom"))
    router.message.register(toggle_room, Command("toggle"))
    return router
