import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from repository import RoomRepository  # noqa: E402
from service import RoomService  # noqa: E402


@pytest.fixture
def service():
    service = RoomService(RoomRepository())
    service.create_room({"number": "101", "room_type": "standard", "floor": 1,
                         "capacity": 2, "price": 3500})
    service.create_room({"number": "201", "room_type": "family", "floor": 2,
                         "capacity": 4, "price": 6000})
    service.create_room({"number": "301", "room_type": "suite", "floor": 3,
                         "capacity": 4, "price": 9000, "status": "booked"})
    return service


@pytest.fixture
def client(service):
    app = create_app(service)
    app.testing = True
    return app.test_client()
