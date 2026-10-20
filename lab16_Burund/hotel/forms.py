from django import forms

from .models import Booking, Guest, Room, RoomType

DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["number", "room_type", "floor", "capacity", "price", "description",
                  "amenities", "is_under_maintenance"]
        widgets = {"amenities": forms.CheckboxSelectMultiple,
                   "description": forms.Textarea(attrs={"rows": 3})}

    def clean_number(self):
        number = self.cleaned_data["number"].strip()
        if not number.isalnum():
            raise forms.ValidationError("Номер комнаты должен состоять из букв и цифр")
        return number

    def clean(self):
        cleaned = super().clean()
        floor, number = cleaned.get("floor"), cleaned.get("number")
        if floor is not None and number and number.isdigit() and not number.startswith(str(floor)):
            self.add_error("number", "Номер комнаты должен начинаться с номера этажа")
        return cleaned


class RoomTypeForm(forms.ModelForm):
    class Meta:
        model = RoomType
        fields = ["name", "description", "base_capacity"]


class GuestForm(forms.ModelForm):
    class Meta:
        model = Guest
        fields = ["full_name", "email", "phone", "passport"]


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ["room", "guest", "check_in", "check_out", "guests_count", "status"]
        widgets = {"check_in": DATE_WIDGET, "check_out": DATE_WIDGET}


class SelfBookingForm(forms.ModelForm):
    """Бронирование номера самим пользователем: гость = текущий пользователь."""

    class Meta:
        model = Booking
        fields = ["check_in", "check_out", "guests_count"]
        widgets = {"check_in": DATE_WIDGET, "check_out": DATE_WIDGET}


class RoomFilterForm(forms.Form):
    SORT_CHOICES = [("number", "по номеру"), ("price", "сначала дешёвые"),
                    ("-price", "сначала дорогие"), ("floor", "по этажу"),
                    ("-capacity", "по вместимости")]

    q = forms.CharField(label="Поиск", required=False,
                        widget=forms.TextInput(attrs={"placeholder": "Номер, описание, удобство"}))
    room_type = forms.ModelChoiceField(RoomType.objects.all(), label="Тип", required=False,
                                       empty_label="Все типы")
    guests = forms.IntegerField(label="Гостей", min_value=1, required=False)
    max_price = forms.DecimalField(label="Цена до", min_value=0, required=False)
    check_in = forms.DateField(label="Заезд", required=False, widget=DATE_WIDGET)
    check_out = forms.DateField(label="Выезд", required=False, widget=DATE_WIDGET)
    sort = forms.ChoiceField(label="Сортировка", choices=SORT_CHOICES, required=False)

    def clean(self):
        cleaned = super().clean()
        check_in, check_out = cleaned.get("check_in"), cleaned.get("check_out")
        if bool(check_in) != bool(check_out):
            raise forms.ValidationError("Для поиска по датам укажите и заезд, и выезд")
        if check_in and check_out and check_out <= check_in:
            raise forms.ValidationError("Дата выезда должна быть позже даты заезда")
        return cleaned
