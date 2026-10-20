from app.repositories.room import RoomRepository


def test_list_with_filters(db):
    with db.session_factory() as session:
        total, rooms = RoomRepository(session).list_rooms(
            {"min_capacity": 4, "is_available": True}, "price", False, 10, 0)
    assert total == 3
    assert [r.number for r in rooms] == ["202", "303", "401"]


def test_statistics(db):
    with db.session_factory() as session:
        stats = RoomRepository(session).statistics()
    assert stats["total"] == 12
    assert stats["min_price"] == 2800
