"""Лабораторная работа №11. Вариант 5. Отель — консольный REST-клиент (requests)."""

import json

import requests

BASE_URL = "http://127.0.0.1:5000"
TIMEOUT = 5

ROOM_TYPES = "standard, deluxe, suite, family"
STATUSES = "free, booked, occupied, maintenance"


def show(response: requests.Response) -> None:
    source = response.headers.get("X-Data-Source")
    print(f"HTTP {response.status_code}" + (f" (источник: {source})" if source else ""))
    if response.status_code == 204:
        print("(нет содержимого)")
        return
    data = response.json()
    if isinstance(data, list):
        print(f"{'id':<4}{'номер':<7}{'тип':<10}{'этаж':<6}{'мест':<6}{'цена':<9}{'статус':<13}"
              f"удобства")
        for r in data:
            print(f"{r['id']:<4}{r['number']:<7}{r['room_type']:<10}{r['floor']:<6}"
                  f"{r['capacity']:<6}{r['price']:<9.0f}{r['status']:<13}"
                  f"{', '.join(r.get('amenities', []))}")
        print(f"Всего: {len(data)}")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def ask_number(label: str, cast=int, allow_empty: bool = False):
    while True:
        text = input(label).strip()
        if allow_empty and not text:
            return None
        try:
            return cast(text)
        except ValueError:
            print("Ошибка: введите число")


def ask_room(partial: bool) -> dict:
    hint = " [Enter — пропустить]" if partial else ""
    data = {}
    number = input(f"Номер комнаты{hint}: ").strip()
    if number or not partial:
        data["number"] = number
    room_type = input(f"Тип ({ROOM_TYPES}){hint}: ").strip()
    if room_type or not partial:
        data["room_type"] = room_type
    for key, label, cast in (("floor", "Этаж", int), ("capacity", "Вместимость", int),
                             ("price", "Цена", float)):
        value = ask_number(f"{label}{hint}: ", cast, allow_empty=partial)
        if value is not None:
            data[key] = value
    status = input(f"Статус ({STATUSES}) [Enter — {'пропустить' if partial else 'free'}]: ").strip()
    if status:
        data["status"] = status
    amenities = input(f"Удобства через запятую{hint}: ").strip()
    if amenities:
        data["amenities"] = [a.strip() for a in amenities.split(",") if a.strip()]
    return data


def ask_booking() -> dict:
    rooms = []
    while True:
        room_id = ask_number("id номера [Enter — закончить]: ", int, allow_empty=True)
        if room_id is None:
            break
        rooms.append({"room_id": room_id, "guests": ask_number("Гостей в номере: ")})
    return {"guest": {"name": input("ФИО гостя: ").strip(),
                      "email": input("E-mail: ").strip()},
            "check_in": input("Заезд (ГГГГ-ММ-ДД): ").strip(),
            "check_out": input("Выезд (ГГГГ-ММ-ДД): ").strip(),
            "rooms": rooms}


def ask_params(names: list[str]) -> dict:
    params = {}
    for name in names:
        value = input(f"{name} [Enter — пропустить]: ").strip()
        if value:
            params[name] = value
    return params


MENU = """
=========================
REST CLIENT — ОТЕЛЬ
=========================
1. Получить список
2. Получить объект
3. Создать
4. Изменить (PUT)
5. Частично изменить (PATCH)
6. Удалить
7. Фильтрация
8. Сортировка
9. Свободные номера (/rooms/available)
10. Статистика
11. Забронировать номера (транзакция)
12. Получить бронирование
13. Отменить бронирование
0. Выход"""


def main() -> None:
    session = requests.Session()
    url = f"{BASE_URL}/rooms"
    while True:
        print(MENU)
        choice = input("Выберите действие: ").strip()
        try:
            if choice == "0":
                break
            elif choice == "1":
                show(session.get(url, timeout=TIMEOUT))
            elif choice == "2":
                show(session.get(f"{url}/{input('id: ').strip()}", timeout=TIMEOUT))
            elif choice == "3":
                show(session.post(url, json=ask_room(False), timeout=TIMEOUT))
            elif choice == "4":
                room_id = input("id: ").strip()
                show(session.put(f"{url}/{room_id}", json=ask_room(False), timeout=TIMEOUT))
            elif choice == "5":
                room_id = input("id: ").strip()
                show(session.patch(f"{url}/{room_id}", json=ask_room(True), timeout=TIMEOUT))
            elif choice == "6":
                show(session.delete(f"{url}/{input('id: ').strip()}", timeout=TIMEOUT))
            elif choice == "7":
                params = ask_params(["room_type", "status", "floor", "min_capacity",
                                     "min_price", "max_price", "amenity"])
                show(session.get(url, params=params, timeout=TIMEOUT))
            elif choice == "8":
                params = {"sort": input("Поле (number, floor, capacity, price): ").strip(),
                          "order": input("Порядок (asc/desc): ").strip() or "asc"}
                show(session.get(url, params=params, timeout=TIMEOUT))
            elif choice == "9":
                params = ask_params(["check_in", "check_out", "guests", "room_type",
                                     "max_price", "amenity"])
                show(session.get(f"{url}/available", params=params, timeout=TIMEOUT))
            elif choice == "10":
                show(session.get(f"{url}/statistics", timeout=TIMEOUT))
            elif choice == "11":
                show(session.post(f"{BASE_URL}/bookings", json=ask_booking(), timeout=TIMEOUT))
            elif choice == "12":
                show(session.get(f"{BASE_URL}/bookings/{input('id брони: ').strip()}",
                                 timeout=TIMEOUT))
            elif choice == "13":
                show(session.post(f"{BASE_URL}/bookings/{input('id брони: ').strip()}/cancel",
                                  timeout=TIMEOUT))
            else:
                print("Неизвестный пункт меню")
        except requests.ConnectionError:
            print("Ошибка: сервер недоступен")
        except requests.Timeout:
            print("Ошибка: превышено время ожидания ответа")


if __name__ == "__main__":
    main()
