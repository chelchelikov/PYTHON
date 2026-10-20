"""Лабораторная работа №13. Вариант 5. Отель — MongoDB + Redis.

Запуск из папки lab13_Burund:  python -m app.main
"""

import json

from redis import RedisError
from pymongo.errors import PyMongoError

from app.cache import CacheError, RedisCache
from app.models import STATES, ROOM_TYPES, VIEWS, Features, Room, ValidationError
from app.mongodb import StorageUnavailable, connect_mongo
from app.redis_client import connect_redis
from app.repository import MongoRepository, NotFoundError
from app.service import RoomService, demo_rooms

MENU = """
===== ОТЕЛЬ: MongoDB + Redis =====
1. Add — добавить номер
2. Find — найти номер по id (cache-aside)
3. List — список номеров
4. Search — поиск по условию
5. Update — изменить номер
6. Delete — удалить номер
7. Statistics — статистика (агрегации)
8. Cache status — состояние Redis
9. Clear cache — очистить кэш
10. Benchmark — MongoDB vs Redis
11. Free rooms — свободные номера (кэш поиска)
0. Exit"""


def print_rooms(rooms: list[Room]) -> None:
    if not rooms:
        print("Ничего не найдено")
    for r in rooms:
        f = r.features
        print(f"  {r.id}  №{r.number:<4} {r.room_type:<9} эт.{r.floor} {r.price:>8.0f} ₽ "
              f"{r.state:<12} {f.area_m2:>4} м², кроватей {f.beds}, вид {f.view}"
              f"{', балкон' if f.balcony else ''} | {', '.join(r.amenities)}")


def ask(prompt: str, cast=str, default=None):
    while True:
        text = input(prompt).strip()
        if not text:
            if default is not None:
                return default
            print("Значение обязательно")
            continue
        try:
            return cast(text)
        except ValueError:
            print("Некорректное значение")


def input_room() -> Room:
    features = Features(ask("Площадь, м²: ", float), ask("Кроватей: ", int),
                        ask(f"Вид ({', '.join(VIEWS)}): "),
                        balcony=ask("Балкон (д/н) [н]: ", default="н") == "д")
    return Room(ask("Номер: "), ask(f"Тип ({', '.join(ROOM_TYPES)}): "), ask("Этаж: ", int),
                ask("Цена: ", float), ask(f"Состояние ({', '.join(STATES)}) [free]: ",
                                          default="free"),
                features, [a.strip() for a in ask("Удобства через запятую [нет]: ",
                                                  default="").split(",") if a.strip()])


def ask_changes() -> dict:
    changes: dict = {}
    price = ask("Новая цена [Enter — без изменений]: ", float, default="")
    if price != "":
        changes["price"] = price
    state = ask(f"Новое состояние ({', '.join(STATES)}) [Enter — без изменений]: ", default="")
    if state:
        changes["state"] = state
    amenity = ask("Добавить удобство [Enter — нет]: ", default="")
    if amenity:
        changes["add_amenity"] = amenity
    return changes


class App:
    def __init__(self, service: RoomService) -> None:
        self.service = service

    def find(self) -> None:
        room = self.service.get_room(ask("id номера: "))
        print(f"Источник: {self.service.last_source.upper()}")
        print_rooms([room])

    def search(self) -> None:
        print("type — по типу, view — по виду, amenity — по удобству, price — диапазон 3000-6000")
        print_rooms(self.service.search(ask("Вид поиска: "), ask("Значение: ")))

    def update(self) -> None:
        room_id = ask("id номера: ")
        changes = ask_changes()
        amenity = changes.pop("add_amenity", None)
        if amenity:
            current = self.service.repository.get(room_id)
            changes["amenities"] = sorted(set(current.amenities) | {amenity})
        if not changes:
            print("Нет изменений")
            return
        print_rooms([self.service.update_room(room_id, changes)])
        print("Кэш номера инвалидирован")

    def statistics(self) -> None:
        stats = self.service.statistics()
        print(f"Всего номеров: {stats['total']}")
        print("По типам:")
        for row in stats["by_type"]:
            print(f"  {row['_id']:<9} {row['count']} шт., средняя {row['avg_price']} ₽, "
                  f"от {row['min_price']} до {row['max_price']}")
        print("По состояниям:", stats["by_state"])
        print("Удобства:", ", ".join(f"{a} ({n})" for a, n in stats["amenities"]))
        print("Самые дорогие:", stats["most_expensive"])
        print("Популярные (Redis Sorted Set):", stats["popular_in_redis"])

    def cache_status(self) -> None:
        print(json.dumps(self.service.cache.status(), ensure_ascii=False, indent=2))
        print("Последние поиски (Redis List):", self.service.cache.recent_searches())

    def benchmark(self) -> None:
        room_id = self.service.list_rooms()[0].id
        print(f"{'Запросов':>9} | {'MongoDB, с':>11} | {'Redis, с':>9} | "
              f"{'Mongo, мс/запр':>14} | {'Redis, мс/запр':>14}")
        for row in self.service.benchmark(room_id):
            print(f"{row['count']:>9} | {row['mongo_total']:>11.3f} | {row['redis_total']:>9.3f} | "
                  f"{row['mongo_avg_ms']:>14.4f} | {row['redis_avg_ms']:>14.4f}")

    def free_rooms(self) -> None:
        room_type = ask(f"Тип ({', '.join(ROOM_TYPES)}) [любой]: ", default="") or None
        beds = ask("Минимум кроватей [1]: ", int, default=1)
        max_price = ask("Цена до [любая]: ", float, default="") or None
        rooms = self.service.free_rooms(room_type, beds, max_price)
        print(f"Источник: {self.service.last_source.upper()}")
        print_rooms(rooms)

    def run(self) -> None:
        actions = {
            "1": lambda: print_rooms([self.service.add_room(input_room())]),
            "2": self.find,
            "3": lambda: print_rooms(self.service.list_rooms()),
            "4": self.search,
            "5": self.update,
            "6": lambda: (self.service.delete_room(ask("id номера: ")), print("Удалено")),
            "7": self.statistics,
            "8": self.cache_status,
            "9": lambda: print("Удалено ключей:", self.service.cache.clear()),
            "10": self.benchmark,
            "11": self.free_rooms,
        }
        while True:
            print(MENU)
            choice = input("Выберите действие: ").strip()
            if choice == "0":
                return
            action = actions.get(choice)
            if action is None:
                print("Неизвестный пункт меню")
                continue
            try:
                action()
            except (ValidationError, NotFoundError, ValueError, CacheError) as error:
                print("Ошибка:", error)
            except (PyMongoError, RedisError) as error:
                print("Ошибка подключения к хранилищу:", error)


def main() -> None:
    try:
        db = connect_mongo()
        redis_client = connect_redis()
    except StorageUnavailable as error:
        print(error)
        print("Запустите сервисы: docker compose up -d")
        return
    repository = MongoRepository(db)
    repository.create_indexes()
    service = RoomService(repository, RedisCache(redis_client))
    if repository.count() == 0:
        repository.insert_many(demo_rooms())
        print(f"Коллекция заполнена: {repository.count()} номеров")
    service.sync_free_set()
    App(service).run()


if __name__ == "__main__":
    main()
