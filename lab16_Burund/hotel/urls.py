from django.urls import path

from . import views

app_name = "hotel"

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("statistics/", views.StatisticsView.as_view(), name="statistics"),
    path("rooms/", views.RoomListView.as_view(), name="room_list"),
    path("rooms/create/", views.RoomCreateView.as_view(), name="room_create"),
    path("rooms/<int:pk>/", views.RoomDetailView.as_view(), name="room_detail"),
    path("rooms/<int:pk>/edit/", views.RoomUpdateView.as_view(), name="room_edit"),
    path("rooms/<int:pk>/delete/", views.RoomDeleteView.as_view(), name="room_delete"),
    path("rooms/<int:pk>/book/", views.book_room, name="room_book"),
    path("room-types/", views.RoomTypeListView.as_view(), name="roomtype_list"),
    path("room-types/create/", views.RoomTypeCreateView.as_view(), name="roomtype_create"),
    path("room-types/<int:pk>/", views.RoomTypeDetailView.as_view(), name="roomtype_detail"),
    path("guests/", views.GuestListView.as_view(), name="guest_list"),
    path("guests/create/", views.GuestCreateView.as_view(), name="guest_create"),
    path("guests/<int:pk>/", views.GuestDetailView.as_view(), name="guest_detail"),
    path("bookings/", views.BookingListView.as_view(), name="booking_list"),
    path("bookings/mine/", views.MyBookingsView.as_view(), name="my_bookings"),
    path("bookings/create/", views.BookingCreateView.as_view(), name="booking_create"),
    path("bookings/<int:pk>/", views.BookingDetailView.as_view(), name="booking_detail"),
    path("bookings/<int:pk>/edit/", views.BookingUpdateView.as_view(), name="booking_edit"),
]
