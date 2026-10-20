# Лабораторная работа №16. Вариант 5. Отель

Веб-приложение гостиницы «Северная звезда» на **Django**: номера и их категории, удобства,
гости, бронирования, поиск свободных номеров по датам, статистика, административная панель,
разграничение доступа.

**Технологии:** Python 3.12+, Django 5/6, Django ORM, шаблоны Django, Class-Based Views,
SQLite (по умолчанию) или PostgreSQL.

## Структура

```
lab16_Burund/
├── manage.py
├── config/                    # settings.py (переменные окружения), urls.py, wsgi/asgi
├── templates/                 # base.html, registration/login.html
└── hotel/                     # приложение
    ├── models.py              # RoomType, Amenity, Room, Guest, Booking
    ├── forms.py               # ModelForm с валидацией, форма фильтров
    ├── views.py               # CBV: списки, карточки, CRUD, статистика; бронирование
    ├── urls.py, admin.py
    ├── management/commands/seed_hotel.py   # демонстрационные данные
    ├── templates/hotel/*.html
    ├── static/hotel/style.css
    └── tests.py               # 19 тестов
```

## Установка и запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_hotel        # 5 категорий, 9 удобств, 24 номера, 8 гостей, 12 броней + пользователи
python manage.py runserver
```

- Приложение: <http://127.0.0.1:8000/>
- Admin: <http://127.0.0.1:8000/admin/>
- Учётные записи после `seed_hotel`: администратор `admin / admin12345`,
  пользователь `user / user12345`. Своего администратора можно создать командой
  `python manage.py createsuperuser`.

### База данных

По умолчанию используется SQLite (`db.sqlite3`). Для PostgreSQL задайте переменную:

```bash
export DATABASE_URL=postgresql://hotel:hotel@localhost:5432/hotel_django
python manage.py migrate && python manage.py seed_hotel
```

Остальные настройки: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` (см. `.env.example`).

### Тесты

```bash
python manage.py test                                              # SQLite
DATABASE_URL=postgresql://hotel:hotel@localhost:5432/hotel_django python manage.py test
```

## Модели и связи

```
RoomType 1───N Room N───M Amenity
                │ 1
                N
User 1──1 Guest 1───N Booking
```

| Модель | Поля | Связи |
|--------|------|-------|
| `RoomType` | name (unique), description, base_capacity | 1:N с `Room` |
| `Amenity` | name (unique) | N:M с `Room` |
| `Room` | number (unique), floor, capacity, price, description, is_under_maintenance | FK `room_type`, M2M `amenities` |
| `Guest` | full_name, email (unique), phone, passport | OneToOne `user` (необязательно) |
| `Booking` | check_in, check_out, guests_count, status, total_price, created_at | FK `room`, FK `guest`; ограничение `check_out > check_in` |

Бизнес-правила бронирования (`Booking.clean`): выезд позже заезда, число гостей не больше
вместимости, номер не на обслуживании, нет пересечения с другими активными бронями.
Стоимость считается при сохранении: цена × количество ночей.

## Страницы

| URL | Назначение | Доступ |
|-----|------------|--------|
| `/` | главная: описание, количество объектов, ссылки, текущий пользователь, поиск по датам | все |
| `/rooms/` | список: поиск `q`, фильтры `room_type`, `guests`, `max_price`, свободные на даты `check_in`/`check_out`, сортировка `sort`, пагинация по 10 | все |
| `/rooms/<id>/` | карточка: категория, удобства, занятые даты, похожие номера, бронирование | все |
| `/rooms/<id>/book/` | бронирование номера на себя | вошедшие пользователи |
| `/rooms/create/`, `/rooms/<id>/edit/`, `/rooms/<id>/delete/` | создание, изменение, удаление с подтверждением | администратор |
| `/room-types/`, `/room-types/<id>/` | категории и их номера | все |
| `/guests/`, `/guests/<id>/` | гости и история бронирований | администратор |
| `/bookings/`, `/bookings/create/`, `/bookings/<id>/edit/` | бронирования | администратор |
| `/bookings/mine/` | мои бронирования | вошедшие пользователи |
| `/statistics/` | 8 показателей, разбивка по категориям, лучшие гости | все |

## Права доступа

- **Анонимный пользователь и обычный пользователь** — просмотр, поиск, фильтрация;
  вошедший пользователь может забронировать номер на себя и видеть свои брони.
- **Администратор** (`is_staff`, группа «Администраторы отеля» со всеми правами `hotel.*`) —
  создание, изменение, удаление номеров, категорий, гостей и бронирований, Django Admin.

Проверка прав — `PermissionRequiredMixin` (`hotel.add_room`, `hotel.change_room`, …):
анонима перенаправляет на вход, пользователя без прав — ответ 403.

## Django Admin

Зарегистрированы все модели. Для `Room` — расширенная настройка: `list_display`,
`list_editable` (цена, обслуживание), `list_filter`, `search_fields`, `ordering`,
`filter_horizontal`, `fieldsets`, inline-бронирования, собственные действия
«Отправить на обслуживание» и «Вернуть с обслуживания». Для `Booking` — `date_hierarchy`,
`autocomplete_fields`, фильтры по статусу и категории.

## Запросы ORM

| Метод | Где |
|-------|-----|
| `all()`, `count()` | главная страница, статистика |
| `filter()`, `exclude()` | фильтры списка, `RoomQuerySet.free_between`, `BookingQuerySet.active` |
| `get()` | `get_object_or_404`, тесты |
| `order_by()` | сортировка списка |
| `exists()` | проверка пересечения броней, номера на обслуживании |
| `aggregate()` | средняя цена, вместимость, сумма броней |
| `annotate()` | число номеров и средняя цена по категориям, траты гостей, категория-лидер |
| связанные объекты | `room.amenities`, `room_type.rooms`, `guest.bookings`, `amenities__name` |

### Проблема N+1

Плохой вариант: `Room.objects.all()` в списке, а в шаблоне `room.room_type.name` и
`room.amenities.all` — на каждую строку ещё 2 запроса, т.е. для 10 номеров 1 + 10 + 10 = 21 запрос.

Улучшенный вариант (`RoomListView.get_queryset`):

```python
Room.objects.select_related("room_type").prefetch_related("amenities")
```

`select_related` подтягивает категорию тем же запросом через JOIN (для FK и OneToOne),
`prefetch_related` загружает удобства всех номеров страницы одним дополнительным запросом
(для M2M и обратных связей). Тест `test_no_n_plus_one_in_room_list` проверяет, что страница
списка выполняется не более чем за 6 запросов.

## Безопасность

CSRF-токены во всех формах (`{% csrf_token %}`, `CsrfViewMiddleware`), встроенная
аутентификация и права Django, хеширование паролей (PBKDF2 — пароли нельзя хранить открыто:
при утечке базы злоумышленник получил бы готовые пароли, которые люди часто используют и на
других сайтах), автоматическое экранирование в шаблонах, секретный ключ из переменной окружения.

## Тесты

19 тестов: главная, список и пагинация, карточка со связанными объектами, поиск, фильтры,
сортировка, свободные номера по датам, статистика; создание, изменение, удаление, валидация
формы, правила бронирования; вход, перенаправление анонима, права пользователя
(403 и бронирование на себя), права администратора; связи моделей и отсутствие N+1.
