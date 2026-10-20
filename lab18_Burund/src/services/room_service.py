from src.exceptions import NotFoundError, OperationNotAllowedError, ValidationError
from src.models import Room

ROOM_TYPES = ("standard", "deluxe", "suite", "family")
MAX_CAPACITY = 6
MAX_PRICE = 1_000_000


def validate_room(number: str, room_type: str, capacity: int, price: float) -> None:
    if not number or not number.strip() or len(number) > 10:
        raise ValidationError("Номер комнаты: от 1 до 10 символов")
    if room_type not in ROOM_TYPES:
        raise ValidationError(f"Тип номера: {', '.join(ROOM_TYPES)}")
    if not isinstance(capacity, int) or not 1 <= capacity <= MAX_CAPACITY:
        raise ValidationError(f"Вместимость: от 1 до {MAX_CAPACITY}")
    if not 0 < price <= MAX_PRICE:
        raise ValidationError(f"Цена: больше 0 и не больше {MAX_PRICE}")


class RoomService:
    def __init__(self, rooms, bookings) -> None:
        self.rooms = rooms
        self.bookings = bookings

    def create_room(self, number: str, room_type: str, capacity: int, price: float) -> Room:
        validate_room(number, room_type, capacity, price)
        if self.rooms.get_by_number(number.strip()) is not None:
            raise ValidationError(f"Номер {number} уже существует")
        return self.rooms.add(Room(number.strip(), room_type, capacity, float(price)))

    def get_room(self, room_id: int) -> Room:
        if not isinstance(room_id, int) or room_id <= 0:
            raise ValidationError(f"Некорректный идентификатор номера: {room_id}")
        room = self.rooms.get(room_id)
        if room is None:
            raise NotFoundError(f"Номер с id={room_id} не найден")
        return room

    def list_rooms(self) -> list[Room]:
        return self.rooms.list()

    def change_price(self, room_id: int, price: float) -> Room:
        room = self.get_room(room_id)
        validate_room(room.number, room.room_type, room.capacity, price)
        room.price_per_night = float(price)
        return self.rooms.update(room)

    def delete_room(self, room_id: int) -> None:
        self.get_room(room_id)
        if self.bookings.active_for_room(room_id):
            raise OperationNotAllowedError("У номера есть активные бронирования")
        self.rooms.delete(room_id)
