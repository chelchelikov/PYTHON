from django.contrib import admin

from .models import Amenity, Booking, Guest, Room, RoomType


class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    fields = ("guest", "check_in", "check_out", "guests_count", "status", "total_price")
    readonly_fields = ("total_price",)
    autocomplete_fields = ("guest",)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    """Расширенная настройка: фильтры, поиск, редактирование в списке, inline, действия."""

    list_display = ("number", "room_type", "floor", "capacity", "price", "is_under_maintenance",
                    "amenities_list")
    list_display_links = ("number",)
    list_editable = ("price", "is_under_maintenance")
    list_filter = ("room_type", "floor", "is_under_maintenance", "amenities")
    search_fields = ("number", "description", "amenities__name")
    ordering = ("number",)
    filter_horizontal = ("amenities",)
    list_select_related = ("room_type",)
    inlines = [BookingInline]
    actions = ["send_to_maintenance", "return_from_maintenance"]
    fieldsets = (
        (None, {"fields": ("number", "room_type", "floor")}),
        ("Параметры", {"fields": ("capacity", "price", "amenities", "is_under_maintenance")}),
        ("Описание", {"fields": ("description",), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("amenities")

    @admin.display(description="удобства")
    def amenities_list(self, obj):
        return ", ".join(a.name for a in obj.amenities.all())

    @admin.action(description="Отправить на обслуживание")
    def send_to_maintenance(self, request, queryset):
        self.message_user(request, f"Обновлено номеров: "
                                   f"{queryset.update(is_under_maintenance=True)}")

    @admin.action(description="Вернуть с обслуживания")
    def return_from_maintenance(self, request, queryset):
        self.message_user(request, f"Обновлено номеров: "
                                   f"{queryset.update(is_under_maintenance=False)}")


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "base_capacity")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "user")
    search_fields = ("full_name", "email", "phone")
    ordering = ("full_name",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "guest", "check_in", "check_out", "status", "total_price")
    list_filter = ("status", "room__room_type", "check_in")
    search_fields = ("guest__full_name", "room__number")
    date_hierarchy = "check_in"
    ordering = ("-check_in",)
    list_select_related = ("room", "guest")
    autocomplete_fields = ("guest",)
    readonly_fields = ("total_price", "created_at")
