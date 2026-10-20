import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (CreateView, DeleteView, DetailView, ListView, TemplateView,
                                  UpdateView)

from .forms import (BookingForm, GuestForm, RoomFilterForm, RoomForm, RoomTypeForm,
                    SelfBookingForm)
from .models import Booking, Guest, Room, RoomType

log = logging.getLogger("hotel")


class IndexView(TemplateView):
    template_name = "hotel/index.html"

    def get_context_data(self, **kwargs):
        today = date.today()
        context = super().get_context_data(**kwargs)
        context.update(
            rooms_count=Room.objects.count(),
            types_count=RoomType.objects.count(),
            guests_count=Guest.objects.count(),
            bookings_count=Booking.objects.active().count(),
            free_today=Room.objects.free_between(today, date.fromordinal(today.toordinal() + 1))
            .count(),
            room_types=RoomType.objects.annotate(rooms_total=Count("rooms")),
        )
        return context


# ---------- номера ----------
class RoomListView(ListView):
    model = Room
    paginate_by = 10
    template_name = "hotel/room_list.html"

    def get_queryset(self):
        # select_related/prefetch_related убирают проблему N+1 (см. README)
        queryset = Room.objects.select_related("room_type").prefetch_related("amenities")
        self.form = RoomFilterForm(self.request.GET or None)
        if not self.form.is_valid():
            return queryset
        data = self.form.cleaned_data
        if data["q"]:
            queryset = queryset.filter(Q(number__icontains=data["q"]) |
                                       Q(description__icontains=data["q"]) |
                                       Q(amenities__name__icontains=data["q"])).distinct()
        if data["room_type"]:
            queryset = queryset.filter(room_type=data["room_type"])
        if data["guests"]:
            queryset = queryset.filter(capacity__gte=data["guests"])
        if data["max_price"] is not None:
            queryset = queryset.filter(price__lte=data["max_price"])
        if data["check_in"] and data["check_out"]:
            queryset = queryset.free_between(data["check_in"], data["check_out"])
        return queryset.order_by(data["sort"] or "number", "number")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = self.form
        query = self.request.GET.copy()
        query.pop("page", None)
        context["query_string"] = query.urlencode()
        return context


class RoomDetailView(DetailView):
    model = Room
    template_name = "hotel/room_detail.html"

    def get_queryset(self):
        return Room.objects.select_related("room_type").prefetch_related("amenities")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bookings = self.object.bookings.select_related("guest")
        context["upcoming"] = bookings.active().filter(check_out__gte=date.today()).order_by(
            "check_in")
        context["booking_form"] = SelfBookingForm()
        context["similar"] = (Room.objects.filter(room_type=self.object.room_type)
                              .exclude(pk=self.object.pk)[:4])
        return context


class AdminRequired(PermissionRequiredMixin):
    raise_exception = False  # анонимов — на страницу входа, пользователей без прав — 403


class RoomCreateView(AdminRequired, CreateView):
    model = Room
    form_class = RoomForm
    permission_required = "hotel.add_room"
    template_name = "hotel/form.html"
    extra_context = {"title": "Новый номер"}

    def form_valid(self, form):
        messages.success(self.request, f"Номер {form.instance.number} создан")
        log.info("Создан номер %s пользователем %s", form.instance.number, self.request.user)
        return super().form_valid(form)


class RoomUpdateView(AdminRequired, UpdateView):
    model = Room
    form_class = RoomForm
    permission_required = "hotel.change_room"
    template_name = "hotel/form.html"
    extra_context = {"title": "Изменение номера"}

    def form_valid(self, form):
        messages.success(self.request, "Изменения сохранены")
        return super().form_valid(form)


class RoomDeleteView(AdminRequired, DeleteView):
    model = Room
    permission_required = "hotel.delete_room"
    template_name = "hotel/confirm_delete.html"
    success_url = reverse_lazy("hotel:room_list")

    def form_valid(self, form):
        if self.object.bookings.exists():
            messages.error(self.request, "У номера есть бронирования — удалить нельзя. "
                                         "Отправьте его на обслуживание.")
            return redirect(self.object)
        messages.success(self.request, f"Номер {self.object.number} удалён")
        log.info("Удалён номер %s пользователем %s", self.object.number, self.request.user)
        return super().form_valid(form)


@login_required
def book_room(request, pk):
    """Пользователь бронирует номер на себя."""
    room = get_object_or_404(Room, pk=pk)
    form = SelfBookingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        guest, _ = Guest.objects.get_or_create(
            user=request.user,
            defaults={"full_name": request.user.get_full_name() or request.user.username,
                      "email": request.user.email or f"{request.user.username}@hotel.local"})
        booking = form.save(commit=False)
        booking.room, booking.guest = room, guest
        try:
            booking.full_clean()
        except ValidationError as error:
            for message in error.messages:
                messages.error(request, message)
        else:
            booking.save()
            messages.success(request, f"Номер {room.number} забронирован, "
                                      f"стоимость {booking.total_price} ₽")
            return redirect("hotel:my_bookings")
    elif request.method == "POST":
        for errors in form.errors.values():
            for message in errors:
                messages.error(request, message)
    return redirect(room)


# ---------- типы номеров ----------
class RoomTypeListView(ListView):
    template_name = "hotel/roomtype_list.html"

    def get_queryset(self):
        return RoomType.objects.annotate(rooms_total=Count("rooms"),
                                         avg_price=Avg("rooms__price"))


class RoomTypeDetailView(DetailView):
    model = RoomType
    template_name = "hotel/roomtype_detail.html"


class RoomTypeCreateView(AdminRequired, CreateView):
    model = RoomType
    form_class = RoomTypeForm
    permission_required = "hotel.add_roomtype"
    template_name = "hotel/form.html"
    extra_context = {"title": "Новый тип номера"}


# ---------- гости (только персонал) ----------
class GuestListView(AdminRequired, ListView):
    permission_required = "hotel.view_guest"
    template_name = "hotel/guest_list.html"
    paginate_by = 10

    def get_queryset(self):
        queryset = Guest.objects.annotate(bookings_total=Count("bookings"),
                                          spent=Sum("bookings__total_price",
                                                    filter=~Q(bookings__status="cancelled"))
                                          ).order_by("full_name")
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(Q(full_name__icontains=q) | Q(email__icontains=q) |
                                       Q(phone__icontains=q))
        return queryset


class GuestDetailView(AdminRequired, DetailView):
    model = Guest
    permission_required = "hotel.view_guest"
    template_name = "hotel/guest_detail.html"


class GuestCreateView(AdminRequired, CreateView):
    model = Guest
    form_class = GuestForm
    permission_required = "hotel.add_guest"
    template_name = "hotel/form.html"
    extra_context = {"title": "Новый гость"}


# ---------- бронирования ----------
class BookingListView(AdminRequired, ListView):
    permission_required = "hotel.view_booking"
    template_name = "hotel/booking_list.html"
    paginate_by = 10

    def get_queryset(self):
        queryset = Booking.objects.select_related("room", "guest")
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        return super().get_context_data(statuses=Booking.Status.choices,
                                        status=self.request.GET.get("status", ""), **kwargs)


class MyBookingsView(LoginRequiredMixin, ListView):
    template_name = "hotel/booking_list.html"
    extra_context = {"mine": True}

    def get_queryset(self):
        return Booking.objects.select_related("room", "guest").filter(
            guest__user=self.request.user)


class BookingDetailView(LoginRequiredMixin, DetailView):
    template_name = "hotel/booking_detail.html"

    def get_queryset(self):
        queryset = Booking.objects.select_related("room__room_type", "guest")
        if self.request.user.has_perm("hotel.view_booking"):
            return queryset
        return queryset.filter(guest__user=self.request.user)


class BookingCreateView(AdminRequired, CreateView):
    model = Booking
    form_class = BookingForm
    permission_required = "hotel.add_booking"
    template_name = "hotel/form.html"
    extra_context = {"title": "Новое бронирование"}

    def get_initial(self):
        return {"room": self.request.GET.get("room")}


class BookingUpdateView(AdminRequired, UpdateView):
    model = Booking
    form_class = BookingForm
    permission_required = "hotel.change_booking"
    template_name = "hotel/form.html"
    extra_context = {"title": "Изменение бронирования"}


# ---------- статистика ----------
class StatisticsView(TemplateView):
    template_name = "hotel/statistics.html"

    def get_context_data(self, **kwargs):
        today = date.today()
        tomorrow = date.fromordinal(today.toordinal() + 1)
        rooms = Room.objects.all()
        active = Booking.objects.active()
        totals = rooms.aggregate(avg_price=Avg("price"), capacity=Sum("capacity"))
        free_today = rooms.free_between(today, tomorrow).count()
        rooms_count = rooms.count()
        leader = (RoomType.objects.annotate(
            bookings_total=Count("rooms__bookings", filter=~Q(rooms__bookings__status="cancelled")))
            .order_by("-bookings_total").first())
        return super().get_context_data(
            rooms_count=rooms_count,
            free_today=free_today,
            occupancy=round((1 - free_today / rooms_count) * 100, 1) if rooms_count else 0,
            avg_price=totals["avg_price"] or 0,
            capacity=totals["capacity"] or 0,
            revenue=active.aggregate(total=Sum("total_price"))["total"] or 0,
            leader=leader,
            cancelled=Booking.objects.filter(status=Booking.Status.CANCELLED).count(),
            has_maintenance=rooms.filter(is_under_maintenance=True).exists(),
            by_type=RoomType.objects.annotate(rooms_total=Count("rooms", distinct=True),
                                              avg_price=Avg("rooms__price"))
            .order_by("-rooms_total"),
            top_guests=Guest.objects.annotate(spent=Sum("bookings__total_price",
                                                        filter=~Q(bookings__status="cancelled")))
            .exclude(spent=None).order_by("-spent")[:5],
            **kwargs)
