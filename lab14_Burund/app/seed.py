"""Заполнение БД демонстрационными номерами: python -m app.seed"""

from app.config import get_settings
from app.database import Database
from app.models.room import Room

ROOMS = [
    ("101", "standard", 1, 2, 3500, True, ["wifi", "tv"]),
    ("102", "standard", 1, 2, 3200, False, ["wifi", "tv"]),
    ("103", "standard", 1, 1, 2800, True, ["wifi"]),
    ("201", "deluxe", 2, 2, 5500, True, ["wifi", "tv", "minibar", "air_conditioning"]),
    ("202", "family", 2, 4, 6000, True, ["wifi", "tv", "kitchen", "crib"]),
    ("203", "deluxe", 2, 3, 5800, False, ["wifi", "tv", "minibar"]),
    ("301", "suite", 3, 4, 9000, False, ["wifi", "tv", "minibar", "bathtub", "sea_view"]),
    ("302", "suite", 3, 3, 8500, True, ["wifi", "tv", "minibar", "bathtub"]),
    ("303", "family", 3, 5, 7000, True, ["wifi", "tv", "kitchen", "crib", "balcony"]),
    ("401", "suite", 4, 4, 12000, True, ["wifi", "tv", "minibar", "bathtub", "sea_view", "jacuzzi"]),
    ("402", "standard", 4, 2, 3900, True, ["wifi", "tv", "air_conditioning"]),
    ("403", "deluxe", 4, 2, 6200, True, ["wifi", "tv", "minibar", "balcony"]),
]


def seed(db: Database) -> int:
    db.create_tables()
    with db.session_factory() as session:
        if session.query(Room).count():
            return 0
        session.add_all(Room(number=n, room_type=t, floor=f, capacity=c, price=p,
                             is_available=a, amenities=am) for n, t, f, c, p, a, am in ROOMS)
        session.commit()
    return len(ROOMS)


if __name__ == "__main__":
    print("Добавлено номеров:", seed(Database(get_settings().database_url)))
