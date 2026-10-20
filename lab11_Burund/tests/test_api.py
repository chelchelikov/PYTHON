def test_list_and_get(client):
    assert len(client.get("/rooms").get_json()) == 12
    data = client.get("/rooms/7").get_json()
    assert data["number"] == "301"
    assert data["photos"][0] == "http://cdn.test/static/images/suite.png"


def test_crud(client):
    response = client.post("/rooms", json={"number": "501", "room_type": "family", "floor": 5,
                                           "capacity": 5, "price": 7500})
    assert response.status_code == 201
    room_id = response.get_json()["id"]
    assert client.patch(f"/rooms/{room_id}", json={"price": 8000}).get_json()["price"] == 8000
    assert client.delete(f"/rooms/{room_id}").status_code == 204
    assert client.get(f"/rooms/{room_id}").status_code == 404


def test_errors(client):
    assert client.get("/rooms/abc").status_code == 400
    assert client.post("/rooms", json={"number": ""}).status_code == 400
    assert client.post("/rooms/1", json={}).status_code == 405
    assert client.delete("/rooms/7").status_code == 409


def test_available_endpoint_uses_cache(client):
    url = "/rooms/available?check_in=2026-11-02&check_out=2026-11-04&guests=4"
    first = client.get(url)
    second = client.get(url)
    assert first.headers["X-Data-Source"] == "db"
    assert second.headers["X-Data-Source"] == "cache"
    assert [r["number"] for r in second.get_json()] == ["202", "303", "401"]


def test_booking_endpoints(client):
    response = client.post("/bookings", json={
        "guest": {"name": "Бурунд", "email": "burund@mail.ru"},
        "check_in": "2026-12-01", "check_out": "2026-12-03",
        "rooms": [{"room_id": 5, "guests": 4}]})
    assert response.status_code == 201
    booking_id = response.get_json()["id"]
    assert client.get(f"/bookings/{booking_id}").get_json()["total_cost"] == 12000
    assert client.post(f"/bookings/{booking_id}/cancel").get_json()["status"] == "cancelled"
    assert client.get("/bookings/999").status_code == 404
