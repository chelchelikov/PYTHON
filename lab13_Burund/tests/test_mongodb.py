import pytest

from app.models import Features, Room, ValidationError
from app.repository import NotFoundError


def new_room(number: str = "601") -> Room:
    return Room(number, "deluxe", 6, 7000, "free", Features(30, 2, "sea", balcony=True),
                ["wifi", "minibar"])


def test_connection_and_seed(repository):
    assert repository.count() == 22


def test_add_and_get(repository):
    room = repository.add(new_room())
    loaded = repository.get(room.id)
    assert loaded.number == "601"
    assert loaded.features.view == "sea"


def test_update(repository):
    room = repository.add(new_room())
    updated = repository.update(room.id, {"price": 7500, "features": {"beds": 3}})
    assert updated.price == 7500
    assert updated.features.beds == 3
    assert updated.features.view == "sea"


def test_delete_and_errors(repository):
    room = repository.add(new_room())
    repository.delete(room.id)
    with pytest.raises(NotFoundError):
        repository.get(room.id)
    with pytest.raises(ValidationError):
        repository.get("not-an-id")
    with pytest.raises(ValidationError):
        repository.add(new_room("101"))  # дубликат номера
    with pytest.raises(ValidationError):
        repository.add(Room("700", "palace", 7, 100, "free", Features(10, 1, "sea")))


def test_filters_and_sorting(repository):
    free_suites = repository.free_rooms("suite")
    assert [r.number for r in free_suites] == ["302", "401", "501"]
    family = repository.free_rooms(min_beds=4, max_price=7000)
    assert [r.number for r in family] == ["204", "303"]
    assert [r.number for r in repository.most_expensive(2)] == ["501", "401"]


def test_nested_and_array_queries(repository):
    assert len(repository.with_view("sea")) == 8
    assert [r.number for r in repository.with_amenity("jacuzzi")] == ["401", "501"]
    assert [r.number for r in repository.with_all_amenities(["kitchen", "jacuzzi"])] == ["501"]


def test_aggregation(repository):
    by_type = {row["_id"]: row for row in repository.stats_by_type()}
    assert by_type["suite"]["count"] == 5
    assert by_type["suite"]["max_price"] == 15000
    assert repository.stats_by_state()["free"] == 14
    assert repository.amenity_popularity()[:2] == [("wifi", 22), ("tv", 21)]
