"""Лабораторная работа №11. Вариант 5. Отель — REST API + SQLite + Redis + CDN.

Переменные окружения:
  HOTEL_DB      путь к файлу БД (по умолчанию hotel.db рядом с app.py)
  REDIS_URL     адрес Redis (по умолчанию redis://localhost:6379/0)
  CDN_BASE_URL  адрес CDN со статикой (по умолчанию локальный edge-сервер)
"""

import os

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from cache import Cache, create_cache
from database import DEFAULT_DB_PATH, Database
from exceptions import ApiError
from repository import BookingRepository, RoomRepository
from routes import api
from service import BookingService, RoomService


def create_app(db: Database | None = None, cache: Cache | None = None,
               cdn_base_url: str | None = None) -> Flask:
    if db is None:
        db = Database(os.environ.get("HOTEL_DB", DEFAULT_DB_PATH))
        if not db.exists():
            db.init(seed=True)
    if cache is None:
        cache = create_cache(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.config["CDN_BASE_URL"] = cdn_base_url or os.environ.get(
        "CDN_BASE_URL", "http://127.0.0.1:8081/static")
    app.config["ROOM_SERVICE"] = RoomService(RoomRepository(db), cache)
    app.config["BOOKING_SERVICE"] = BookingService(BookingRepository(db), cache)
    app.register_blueprint(api)

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return jsonify({"error": error.message, "code": error.code}), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        code = (error.name or "error").upper().replace(" ", "_")
        return jsonify({"error": error.description, "code": code}), error.code

    return app


if __name__ == "__main__":
    application = create_app()
    print("Кэш:", application.config["ROOM_SERVICE"].cache.name)
    application.run(host="127.0.0.1", port=5000)
