from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse


class RoomType(models.Model):
    """Категория номера (стандарт, люкс...)."""

    name = models.CharField("название", max_length=50, unique=True)
    description = models.TextField("описание", blank=True)
    base_capacity = models.PositiveSmallIntegerField("типовая вместимость", default=2)

    class Meta:
        ordering = ["name"]
        verbose_name = "тип номера"
        verbose_name_plural = "типы номеров"

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("hotel:roomtype_detail", args=[self.pk])


class Amenity(models.Model):
    name = models.CharField("название", max_length=50, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "удобство"
        verbose_name_plural = "удобства"

    def __str__(self) -> str:
        return self.name


class RoomQuerySet(models.QuerySet):
    def free_between(self, check_in, check_out):
        """Номера без активных бронирований, пересекающихся с периодом [check_in, check_out)."""
        busy = Booking.objects.active().filter(check_in__lt=check_out, check_out__gt=check_in)
        return self.exclude(is_under_maintenance=True).exclude(bookings__in=busy).distinct()


class Room(models.Model):
    number = models.CharField("номер", max_length=10, unique=True)
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT, related_name="rooms",
                                  verbose_name="тип")
    floor = models.PositiveSmallIntegerField("этаж")
    capacity = models.PositiveSmallIntegerField("вместимость",
                                                validators=[MinValueValidator(1)])
    price = models.DecimalField("цена за ночь", max_digits=10, decimal_places=2,
                                validators=[MinValueValidator(Decimal("1"))])
    description = models.TextField("описание", blank=True)
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="rooms",
                                       verbose_name="удобства")
    is_under_maintenance = models.BooleanField("на обслуживании", default=False)

    objects = RoomQuerySet.as_manager()

    class Meta:
        ordering = ["number"]
        verbose_name = "номер"
        verbose_name_plural = "номера"

    def __str__(self) -> str:
        return f"№{self.number} ({self.room_type})"

    def get_absolute_url(self) -> str:
        return reverse("hotel:room_detail", args=[self.pk])

    def is_free(self, check_in, check_out) -> bool:
        return Room.objects.free_between(check_in, check_out).filter(pk=self.pk).exists()


class Guest(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="guest", verbose_name="пользователь")
    full_name = models.CharField("ФИО", max_length=100)
    email = models.EmailField("e-mail", unique=True)
    phone = models.CharField("телефон", max_length=20, blank=True)
    passport = models.CharField("паспорт", max_length=20, blank=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name = "гость"
        verbose_name_plural = "гости"

    def __str__(self) -> str:
        return self.full_name

    def get_absolute_url(self) -> str:
        return reverse("hotel:guest_detail", args=[self.pk])


class BookingQuerySet(models.QuerySet):
    def active(self):
        return self.exclude(status=Booking.Status.CANCELLED)


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "подтверждено"
        CHECKED_IN = "checked_in", "гость заселён"
        COMPLETED = "completed", "завершено"
        CANCELLED = "cancelled", "отменено"

    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="bookings",
                             verbose_name="номер")
    guest = models.ForeignKey(Guest, on_delete=models.PROTECT, related_name="bookings",
                              verbose_name="гость")
    check_in = models.DateField("заезд")
    check_out = models.DateField("выезд")
    guests_count = models.PositiveSmallIntegerField("гостей", default=1,
                                                    validators=[MinValueValidator(1)])
    status = models.CharField("статус", max_length=20, choices=Status.choices,
                              default=Status.CONFIRMED)
    total_price = models.DecimalField("стоимость", max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField("создано", auto_now_add=True)

    objects = BookingQuerySet.as_manager()

    class Meta:
        ordering = ["-check_in"]
        verbose_name = "бронирование"
        verbose_name_plural = "бронирования"
        constraints = [
            models.CheckConstraint(condition=Q(check_out__gt=models.F("check_in")),
                                   name="booking_dates_order"),
        ]

    def __str__(self) -> str:
        return f"Бронь #{self.pk}: {self.room} — {self.guest}"

    def get_absolute_url(self) -> str:
        return reverse("hotel:booking_detail", args=[self.pk])

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    def clean(self) -> None:
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            raise ValidationError({"check_out": "Дата выезда должна быть позже даты заезда"})
        if not (self.room_id and self.check_in and self.check_out):
            return
        if self.guests_count and self.guests_count > self.room.capacity:
            raise ValidationError({"guests_count":
                                   f"Номер рассчитан максимум на {self.room.capacity} гостей"})
        if self.room.is_under_maintenance:
            raise ValidationError({"room": "Номер на обслуживании"})
        overlapping = (Booking.objects.active().filter(room_id=self.room_id,
                                                       check_in__lt=self.check_out,
                                                       check_out__gt=self.check_in)
                       .exclude(pk=self.pk))
        if self.status != self.Status.CANCELLED and overlapping.exists():
            raise ValidationError("Номер уже забронирован на выбранные даты")

    def save(self, *args, **kwargs) -> None:
        self.total_price = self.room.price * self.nights
        super().save(*args, **kwargs)
