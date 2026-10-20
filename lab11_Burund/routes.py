from flask import Blueprint, current_app, jsonify, request

from exceptions import ValidationError
from schemas import parse_query

api = Blueprint("api", __name__)


def rooms():
    return current_app.config["ROOM_SERVICE"]


def bookings():
    return current_app.config["BOOKING_SERVICE"]


def cdn() -> str:
    return current_app.config["CDN_BASE_URL"]


def json_body():
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError("Ожидается тело запроса в формате JSON")
    return data


def parse_id(raw: str) -> int:
    if not raw.isdigit() or int(raw) == 0:
        raise ValidationError(f"Некорректный идентификатор: {raw}")
    return int(raw)


def with_source(response, source: str):
    response.headers["X-Data-Source"] = source
    return response


@api.get("/rooms")
def list_rooms():
    return jsonify([r.to_dict(cdn()) for r in rooms().get_rooms(parse_query(request.args))])


@api.get("/rooms/available")
def available_rooms():
    result = rooms().available_rooms(parse_query(request.args))
    return with_source(jsonify([r.to_dict(cdn()) for r in result]), rooms().last_source)


@api.get("/rooms/statistics")
def statistics():
    return jsonify(rooms().statistics())


@api.get("/rooms/<room_id>")
def get_room(room_id):
    room = rooms().get_room(parse_id(room_id))
    data = room.to_dict(cdn())
    data["views"] = rooms().views(room.id)
    return with_source(jsonify(data), rooms().last_source)


@api.post("/rooms")
def create_room():
    room = rooms().create_room(json_body())
    response = jsonify(room.to_dict(cdn()))
    response.status_code = 201
    response.headers["Location"] = f"/rooms/{room.id}"
    return response


@api.put("/rooms/<room_id>")
def update_room(room_id):
    return jsonify(rooms().update_room(parse_id(room_id), json_body()).to_dict(cdn()))


@api.patch("/rooms/<room_id>")
def patch_room(room_id):
    return jsonify(rooms().patch_room(parse_id(room_id), json_body()).to_dict(cdn()))


@api.delete("/rooms/<room_id>")
def delete_room(room_id):
    rooms().delete_room(parse_id(room_id))
    return "", 204


@api.post("/bookings")
def create_booking():
    booking = bookings().create_booking(json_body())
    response = jsonify(booking.to_dict())
    response.status_code = 201
    response.headers["Location"] = f"/bookings/{booking.id}"
    return response


@api.get("/bookings/<booking_id>")
def get_booking(booking_id):
    return jsonify(bookings().get_booking(parse_id(booking_id)).to_dict())


@api.post("/bookings/<booking_id>/cancel")
def cancel_booking(booking_id):
    return jsonify(bookings().cancel_booking(parse_id(booking_id)).to_dict())
