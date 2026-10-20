"""Лабораторная работа №10. Вариант 5. Отель — REST API (Flask)."""

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from exceptions import ApiError
from repository import RoomRepository
from routes import rooms_bp
from service import RoomService

DEMO_ROOMS = [
    {"number": "101", "room_type": "standard", "floor": 1, "capacity": 2, "price": 3500},
    {"number": "102", "room_type": "standard", "floor": 1, "capacity": 2, "price": 3200,
     "status": "occupied"},
    {"number": "201", "room_type": "deluxe", "floor": 2, "capacity": 2, "price": 5500},
    {"number": "202", "room_type": "family", "floor": 2, "capacity": 4, "price": 6000},
    {"number": "301", "room_type": "suite", "floor": 3, "capacity": 4, "price": 9000,
     "status": "booked"},
    {"number": "302", "room_type": "suite", "floor": 3, "capacity": 3, "price": 8500},
]


def create_app(service: RoomService | None = None, demo_data: bool = True) -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False
    if service is None:
        service = RoomService(RoomRepository())
        if demo_data:
            for room in DEMO_ROOMS:
                service.create_room(room)
    app.config["ROOM_SERVICE"] = service
    app.register_blueprint(rooms_bp)

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return jsonify({"error": error.message, "code": error.code}), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        code = (error.name or "error").upper().replace(" ", "_")
        return jsonify({"error": error.description, "code": code}), error.code

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
