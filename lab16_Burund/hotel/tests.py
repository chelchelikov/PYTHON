from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Amenity, Booking, Guest, Room, RoomType

TODAY = date.today()


class HotelTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser("admin", "a@a.ru", "admin12345")
        cls.user = User.objects.create_user("user", "u@u.ru", "user12345")
        cls.standard = RoomType.objects.create(name="Стандарт", base_capacity=2)
        cls.suite = RoomType.objects.create(name="Люкс", base_capacity=3)
        wifi = Amenity.objects.create(name="Wi-Fi")
        cls.bath = Amenity.objects.create(name="Ванна")
        for index in range(12):  # 12 номеров → 2 страницы по 10
            room = Room.objects.create(number=f"1{index:02d}", room_type=cls.standard, floor=1,
                                       capacity=2, price=Decimal(3000 + index * 100))
            room.amenities.add(wifi)
        cls.lux = Room.objects.create(number="301", room_type=cls.suite, floor=3, capacity=4,
                                      price=Decimal(9000), description="Вид на море")
        cls.lux.amenities.add(wifi, cls.bath)
        cls.guest = Guest.objects.create(full_name="Иванов Иван", email="ivanov@mail.ru")
        cls.booking = Booking.objects.create(room=cls.lux, guest=cls.guest,
                                             check_in=TODAY + timedelta(days=2),
                                             check_out=TODAY + timedelta(days=5),
                                             guests_count=2)

    def login_admin(self):
        self.client.login(username="admin", password="admin12345")

    def login_user(self):
        self.client.login(username="user", password="user12345")


class PageTests(HotelTestCase):
    def test_index(self):
        response = self.client.get(reverse("hotel:index"))
        self.assertContains(response, "Северная звезда")
        self.assertEqual(response.context["rooms_count"], 13)

    def test_list_and_pagination(self):
        response = self.client.get(reverse("hotel:room_list"))
        self.assertEqual(len(response.context["page_obj"]), 10)
        page2 = self.client.get(reverse("hotel:room_list"), {"page": 2})
        self.assertEqual(len(page2.context["page_obj"]), 3)

    def test_detail_shows_related(self):
        response = self.client.get(self.lux.get_absolute_url())
        self.assertContains(response, "Ванна")
        self.assertContains(response, "Люкс")
        self.assertEqual(list(response.context["upcoming"]), [self.booking])

    def test_search(self):
        response = self.client.get(reverse("hotel:room_list"), {"q": "море"})
        self.assertEqual([r.number for r in response.context["page_obj"]], ["301"])

    def test_filters(self):
        response = self.client.get(reverse("hotel:room_list"),
                                   {"room_type": self.standard.pk, "max_price": 3200})
        self.assertEqual([r.number for r in response.context["page_obj"]],
                         ["100", "101", "102"])
        response = self.client.get(reverse("hotel:room_list"), {"guests": 3})
        self.assertEqual([r.number for r in response.context["page_obj"]], ["301"])

    def test_sorting(self):
        response = self.client.get(reverse("hotel:room_list"), {"sort": "-price"})
        self.assertEqual(response.context["page_obj"][0].number, "301")
        response = self.client.get(reverse("hotel:room_list"), {"sort": "price"})
        self.assertEqual(response.context["page_obj"][0].number, "100")

    def test_free_rooms_by_dates(self):
        params = {"check_in": TODAY + timedelta(days=3), "check_out": TODAY + timedelta(days=4)}
        response = self.client.get(reverse("hotel:room_list"), {**params, "guests": 3})
        self.assertEqual(list(response.context["page_obj"]), [])
        params = {"check_in": TODAY + timedelta(days=5), "check_out": TODAY + timedelta(days=7)}
        response = self.client.get(reverse("hotel:room_list"), {**params, "guests": 3})
        self.assertEqual([r.number for r in response.context["page_obj"]], ["301"])

    def test_statistics(self):
        response = self.client.get(reverse("hotel:statistics"))
        self.assertEqual(response.context["rooms_count"], 13)
        self.assertEqual(response.context["revenue"], Decimal(27000))
        self.assertEqual(response.context["leader"], self.suite)


class CrudTests(HotelTestCase):
    def test_create(self):
        self.login_admin()
        response = self.client.post(reverse("hotel:room_create"), {
            "number": "401", "room_type": self.suite.pk, "floor": 4, "capacity": 3,
            "price": "11000", "amenities": [self.bath.pk]})
        room = Room.objects.get(number="401")
        self.assertRedirects(response, room.get_absolute_url())
        self.assertEqual(list(room.amenities.all()), [self.bath])

    def test_update(self):
        self.login_admin()
        url = reverse("hotel:room_edit", args=[self.lux.pk])
        self.assertContains(self.client.get(url), 'value="301"')
        self.client.post(url, {"number": "301", "room_type": self.suite.pk, "floor": 3,
                               "capacity": 4, "price": "9500"})
        self.lux.refresh_from_db()
        self.assertEqual(self.lux.price, Decimal("9500"))

    def test_delete(self):
        self.login_admin()
        room = Room.objects.get(number="100")
        url = reverse("hotel:room_delete", args=[room.pk])
        self.assertContains(self.client.get(url), "действительно хотите удалить")
        self.client.post(url)
        self.assertFalse(Room.objects.filter(number="100").exists())
        self.client.post(reverse("hotel:room_delete", args=[self.lux.pk]))
        self.assertTrue(Room.objects.filter(pk=self.lux.pk).exists())  # есть брони

    def test_validation(self):
        self.login_admin()
        response = self.client.post(reverse("hotel:room_create"), {
            "number": "5-01", "room_type": self.suite.pk, "floor": 5, "capacity": 0,
            "price": "-1"})
        form = response.context["form"]
        self.assertIn("number", form.errors)
        self.assertIn("capacity", form.errors)
        self.assertIn("price", form.errors)

    def test_booking_rules(self):
        overlapping = Booking(room=self.lux, guest=self.guest,
                              check_in=TODAY + timedelta(days=4),
                              check_out=TODAY + timedelta(days=6))
        with self.assertRaises(ValidationError):
            overlapping.full_clean()
        too_many = Booking(room=self.lux, guest=self.guest, guests_count=5,
                           check_in=TODAY + timedelta(days=10),
                           check_out=TODAY + timedelta(days=11))
        with self.assertRaises(ValidationError):
            too_many.full_clean()
        self.assertEqual(self.booking.total_price, Decimal(27000))


class AccessTests(HotelTestCase):
    def test_login(self):
        response = self.client.post(reverse("login"), {"username": "user",
                                                       "password": "user12345"})
        self.assertRedirects(response, reverse("hotel:index"))
        self.client.logout()
        bad = self.client.post(reverse("login"), {"username": "user", "password": "wrong"})
        self.assertEqual(bad.status_code, 200)
        self.assertFalse(bad.context["user"].is_authenticated)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("hotel:room_create"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('hotel:room_create')}")

    def test_regular_user_rights(self):
        self.login_user()
        self.assertEqual(self.client.get(reverse("hotel:room_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("hotel:room_create")).status_code, 403)
        self.assertEqual(self.client.post(reverse("hotel:room_delete",
                                                  args=[self.lux.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("hotel:guest_list")).status_code, 403)
        # пользователь может забронировать номер на себя
        response = self.client.post(reverse("hotel:room_book", args=[self.lux.pk]), {
            "check_in": TODAY + timedelta(days=10), "check_out": TODAY + timedelta(days=12),
            "guests_count": 2})
        self.assertRedirects(response, reverse("hotel:my_bookings"))
        self.assertTrue(Booking.objects.filter(guest__user=self.user).exists())

    def test_admin_rights(self):
        self.login_admin()
        for name in ("hotel:room_create", "hotel:guest_list", "hotel:booking_list",
                     "hotel:booking_create"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("admin:hotel_room_changelist")).status_code, 200)


class OrmTests(HotelTestCase):
    def test_relations(self):
        self.assertEqual(self.suite.rooms.count(), 1)
        self.assertEqual(self.bath.rooms.get(), self.lux)
        self.assertEqual(self.guest.bookings.first().room, self.lux)
        self.assertTrue(Room.objects.filter(amenities__name="Ванна").exists())
        self.assertEqual(Room.objects.exclude(room_type=self.standard).count(), 1)

    def test_no_n_plus_one_in_room_list(self):
        with CaptureQueriesContext(connection) as queries:
            self.client.get(reverse("hotel:room_list"))
        # постраничный COUNT, номера с типами (JOIN), удобства одним запросом + сессия/фильтры
        self.assertLessEqual(len(queries), 6)
