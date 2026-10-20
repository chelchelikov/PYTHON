"""NoSQL-часть: Redis как кэш и альтернативное хранилище для поиска свободных номеров.

1. Базовые операции: SET, GET, EXPIRE/TTL, INCR, DELETE.
2. Операция REST API «свободные номера» через структуры Redis
   (хэши номеров, множество свободных, отсортированное множество по цене)
   и сравнение с SQL-реализацией.

Запуск: redis-server должен быть запущен; python nosql/redis_demo.py
"""

import os
import sys
import time

import redis

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database  # noqa: E402
from repository import RoomRepository  # noqa: E402

PREFIX = "demo:hotel:"


def basic_operations(r: redis.Redis) -> None:
    print("=== Базовые операции Redis ===")
    r.set(PREFIX + "room:101:status", "free")
    print("SET + GET room:101:status ->", r.get(PREFIX + "room:101:status"))

    r.set(PREFIX + "search:last", "guests=2&max_price=6000")
    r.expire(PREFIX + "search:last", 60)
    print("EXPIRE 60, TTL search:last ->", r.ttl(PREFIX + "search:last"), "с")

    r.delete(PREFIX + "views:room:101")
    for _ in range(3):
        views = r.incr(PREFIX + "views:room:101")
    print("INCR views:room:101 трижды ->", views)

    r.delete(PREFIX + "room:101:status")
    print("DELETE room:101:status, GET ->", r.get(PREFIX + "room:101:status"))


def load_rooms(r: redis.Redis, repo: RoomRepository) -> None:
    """Копирует номера из SQL в Redis-структуры."""
    for key in r.scan_iter(PREFIX + "rooms:*"):
        r.delete(key)
    pipe = r.pipeline()
    for room in repo.get_all():
        pipe.hset(f"{PREFIX}rooms:{room.id}", mapping={
            "number": room.number, "type": room.room_type, "capacity": room.capacity,
            "price": room.price, "status": room.status})
        pipe.zadd(PREFIX + "rooms:by_price", {room.id: room.price})
        if room.status == "free":
            pipe.sadd(PREFIX + "rooms:free", room.id)
    pipe.execute()


def available_redis(r: redis.Redis, guests: int, max_price: float) -> list[str]:
    candidates = r.zrangebyscore(PREFIX + "rooms:by_price", 0, max_price)
    free = r.smembers(PREFIX + "rooms:free")
    result = []
    for room_id in candidates:  # уже отсортированы по цене
        if room_id in free:
            room = r.hgetall(f"{PREFIX}rooms:{room_id}")
            if int(room["capacity"]) >= guests:
                result.append(room["number"])
    return result


def main() -> None:
    r = redis.Redis(decode_responses=True)
    try:
        r.ping()
    except redis.ConnectionError:
        print("Redis не запущен: выполните redis-server")
        return

    basic_operations(r)

    db = Database(os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.db"))
    db.init(seed=True)
    repo = RoomRepository(db)
    load_rooms(r, repo)

    print("\n=== Свободные номера на 2+ гостей до 7000 ₽ ===")
    start = time.perf_counter()
    sql = [room.number for room in repo.find_available({"guests": 2, "max_price": 7000})]
    sql_time = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    nosql = available_redis(r, 2, 7000)
    redis_time = (time.perf_counter() - start) * 1000
    print(f"SQLite: {sql} — {sql_time:.2f} мс")
    print(f"Redis:  {nosql} — {redis_time:.2f} мс")
    print("Результаты совпадают:", sql == nosql)
    os.remove(db.path)


if __name__ == "__main__":
    main()
