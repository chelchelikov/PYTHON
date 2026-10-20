from aiogram import Router

from handlers import admin, booking, common, fallback, my_bookings, rooms


def setup_routers() -> Router:
    """Создаёт новое дерево роутеров (для каждого Dispatcher — своё)."""
    root = Router(name="root")
    # common первым: /cancel и /start работают в любом состоянии FSM;
    # fallback последним: ловит всё, что не обработали остальные
    root.include_routers(common.create_router(), admin.create_router(), rooms.create_router(),
                         booking.create_router(), my_bookings.create_router(),
                         fallback.create_router())
    return root
