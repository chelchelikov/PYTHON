"""Заполнение БД демонстрационными данными: python manage.py seed_hotel"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from hotel.models import Amenity, Booking, Guest, Room, RoomType

TYPES = [
    ("Стандарт", "Уютный номер с одной двуспальной или двумя односпальными кроватями", 2, 3200),
    ("Комфорт", "Улучшенный номер с рабочей зоной", 2, 4500),
    ("Семейный", "Просторный номер для семьи с детьми", 4, 6000),
    ("Люкс", "Двухкомнатный номер с гостиной", 3, 9000),
    ("Президентский", "Лучший номер отеля с панорамным видом", 4, 18000),
]
AMENITIES = ["Wi-Fi", "Кондиционер", "Мини-бар", "Ванна", "Сейф", "Балкон", "Вид на море",
             "Кухня", "Детская кроватка"]
GUESTS = [
    ("Иванов Иван Иванович", "ivanov@mail.ru", "+7 900 111-22-33"),
    ("Петрова Анна Сергеевна", "petrova@mail.ru", "+7 900 222-33-44"),
    ("Сидоров Пётр Петрович", "sidorov@mail.ru", "+7 900 333-44-55"),
    ("Кузнецова Мария Олеговна", "kuz@mail.ru", "+7 900 444-55-66"),
    ("Смирнов Олег Викторович", "smirnov@mail.ru", "+7 900 555-66-77"),
    ("Волкова Елена Андреевна", "volkova@mail.ru", "+7 900 666-77-88"),
    ("Морозов Дмитрий Ильич", "morozov@mail.ru", "+7 900 777-88-99"),
]


class Command(BaseCommand):
    help = "Создаёт пользователей, категории, номера, гостей и бронирования"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="удалить существующие данные")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            Booking.objects.all().delete()
            Guest.objects.all().delete()
            Room.objects.all().delete()
            RoomType.objects.all().delete()
            Amenity.objects.all().delete()
        if Room.objects.exists():
            self.stdout.write("Данные уже есть (используйте --reset)")
            return

        random.seed(5)
        users = self.create_users()
        amenities = {name: Amenity.objects.create(name=name) for name in AMENITIES}
        types = {name: RoomType.objects.create(name=name, description=text, base_capacity=cap)
                 for name, text, cap, _ in TYPES}
        base_prices = {name: price for name, _, _, price in TYPES}

        plan = (["Стандарт"] * 8 + ["Комфорт"] * 6 + ["Семейный"] * 4 + ["Люкс"] * 4
                + ["Президентский"] * 2)
        rooms = []
        for index, type_name in enumerate(plan):
            floor = index // 6 + 1
            room = Room.objects.create(
                number=f"{floor}{index % 6 + 1:02d}", room_type=types[type_name], floor=floor,
                capacity=types[type_name].base_capacity + (1 if index % 5 == 0 else 0),
                price=Decimal(base_prices[type_name] + floor * 200),
                description=f"{type_name}, {floor} этаж",
                is_under_maintenance=index in (5, 17))
            extra = random.sample(AMENITIES[1:], k=min(2 + plan.index(type_name) % 4, 6))
            room.amenities.set([amenities["Wi-Fi"]] + [amenities[a] for a in extra])
            rooms.append(room)

        guests = [Guest.objects.create(full_name=n, email=e, phone=p) for n, e, p in GUESTS]
        guests.append(Guest.objects.create(user=users["user"], full_name="Демо Пользователь",
                                           email="user@hotel.local"))
        today = date.today()
        offsets = [(-10, 3), (-2, 4), (0, 2), (1, 5), (3, 2), (5, 7), (7, 3), (10, 4),
                   (14, 2), (20, 5), (-30, 4), (-20, 2)]
        free_rooms = [r for r in rooms if not r.is_under_maintenance]
        for number, (start, nights) in enumerate(offsets):
            check_in = today + timedelta(days=start)
            check_out = check_in + timedelta(days=nights)
            if check_out < today:
                status = Booking.Status.COMPLETED
            elif check_in <= today:
                status = Booking.Status.CHECKED_IN
            else:
                status = Booking.Status.CONFIRMED
            if number == 9:
                status = Booking.Status.CANCELLED
            Booking.objects.create(room=free_rooms[number * 2 % len(free_rooms)],
                                   guest=guests[number % len(guests)], check_in=check_in,
                                   check_out=check_out, guests_count=1, status=status)
        self.stdout.write(self.style.SUCCESS(
            f"Создано: категорий {len(types)}, номеров {len(rooms)}, гостей {len(guests)}, "
            f"бронирований {Booking.objects.count()}"))

    def create_users(self):
        User = get_user_model()
        admins, _ = Group.objects.get_or_create(name="Администраторы отеля")
        admins.permissions.set(Permission.objects.filter(content_type__app_label="hotel"))
        admin, created = User.objects.get_or_create(username="admin",
                                                    defaults={"is_staff": True,
                                                              "is_superuser": True})
        if created:
            admin.set_password("admin12345")
            admin.save()
        admin.groups.add(admins)
        user, created = User.objects.get_or_create(username="user",
                                                   defaults={"email": "user@hotel.local"})
        if created:
            user.set_password("user12345")
            user.save()
        return {"admin": admin, "user": user}
