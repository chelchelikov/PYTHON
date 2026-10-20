def test_cache_aside_and_invalidation(service, repository):
    room_id = repository.get_by_number("201").id

    service.get_room(room_id)                       # 1. MongoDB
    assert service.last_source == "mongodb"
    assert service.cache.exists(f"room:{room_id}")  # 2. положен в Redis
    service.get_room(room_id)                       # 3. из Redis
    assert service.last_source == "redis"

    service.update_room(room_id, {"price": 5900})   # 4. изменение
    assert not service.cache.exists(f"room:{room_id}")  # 5. кэш инвалидирован

    room = service.get_room(room_id)                # 6. снова MongoDB
    assert service.last_source == "mongodb"
    assert room.price == 5900                       # 7. свежие данные
    assert service.cache.get_json(f"room:{room_id}")["price"] == 5900


def test_search_cache_and_free_set(service, repository):
    first = service.free_rooms("suite")
    service.free_rooms("suite")
    assert service.last_source == "redis"
    room = first[0]
    assert service.cache.is_free(room.id)
    service.update_room(room.id, {"state": "booked"})
    assert not service.cache.is_free(room.id)
    after = service.free_rooms("suite")
    assert service.last_source == "mongodb"
    assert len(after) == len(first) - 1


def test_benchmark(service, repository):
    results = service.benchmark(repository.get_by_number("101").id, counts=(10, 50))
    assert [row["count"] for row in results] == [10, 50]
    assert all(row["mongo_total"] > 0 and row["redis_total"] > 0 for row in results)
