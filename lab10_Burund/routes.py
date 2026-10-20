from flask import Blueprint, current_app, jsonify, request

from exceptions import ValidationError
from schemas import parse_query

rooms_bp = Blueprint("rooms", __name__)


def service():
    return current_app.config["ROOM_SERVICE"]


def json_body():
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError("Ожидается тело запроса в формате JSON (Content-Type: application/json)")
    return data


@rooms_bp.get("/rooms")
def list_rooms():
    rooms = service().get_rooms(parse_query(request.args))
    return jsonify([room.to_dict() for room in rooms])


@rooms_bp.get("/rooms/available")
def available_rooms():
    rooms = service().available_rooms(parse_query(request.args))
    return jsonify([room.to_dict() for room in rooms])


@rooms_bp.get("/rooms/statistics")
def rooms_statistics():
    return jsonify(service().statistics())


@rooms_bp.get("/rooms/<room_id>")
def get_room(room_id):
    return jsonify(service().get_room(parse_id(room_id)).to_dict())


@rooms_bp.post("/rooms")
def create_room():
    room = service().create_room(json_body())
    response = jsonify(room.to_dict())
    response.status_code = 201
    response.headers["Location"] = f"/rooms/{room.id}"
    return response


@rooms_bp.put("/rooms/<room_id>")
def update_room(room_id):
    return jsonify(service().update_room(parse_id(room_id), json_body()).to_dict())


@rooms_bp.patch("/rooms/<room_id>")
def patch_room(room_id):
    return jsonify(service().patch_room(parse_id(room_id), json_body()).to_dict())


@rooms_bp.delete("/rooms/<room_id>")
def delete_room(room_id):
    service().delete_room(parse_id(room_id))
    return "", 204


def parse_id(raw: str) -> int:
    if not raw.isdigit() or int(raw) == 0:
        raise ValidationError(f"Некорректный идентификатор: {raw}")
    return int(raw)
