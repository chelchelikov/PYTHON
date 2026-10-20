from aiogram.fsm.state import State, StatesGroup


class BookingForm(StatesGroup):
    """Многошаговое бронирование: 6 состояний."""

    check_in = State()
    check_out = State()
    guests = State()
    room_type = State()
    room = State()
    confirm = State()


class SearchForm(StatesGroup):
    check_in = State()
    check_out = State()
    guests = State()


class ChangeDatesForm(StatesGroup):
    check_in = State()
    check_out = State()
