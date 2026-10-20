NEW_ROOM = {"number": "401", "room_type": "deluxe", "floor": 4, "capacity": 2, "price": 5500}


def test_get_list(client):
    response = client.get("/rooms")
    assert response.status_code == 200
    assert len(response.get_json()) == 3


def test_get_one(client):
    response = client.get("/rooms/2")
    assert response.status_code == 200
    assert response.get_json()["number"] == "201"


def test_create(client):
    response = client.post("/rooms", json=NEW_ROOM)
    assert response.status_code == 201
    assert response.headers["Location"] == "/rooms/4"
    assert response.get_json()["status"] == "free"


def test_put(client):
    response = client.put("/rooms/1", json={**NEW_ROOM, "number": "101", "price": 4000})
    assert response.status_code == 200
    assert response.get_json()["price"] == 4000


def test_patch(client):
    response = client.patch("/rooms/1", json={"status": "maintenance"})
    assert response.status_code == 200
    assert response.get_json()["status"] == "maintenance"
    assert response.get_json()["price"] == 3500


def test_delete(client):
    assert client.delete("/rooms/1").status_code == 204
    assert client.get("/rooms/1").status_code == 404


def test_404_format(client):
    response = client.get("/rooms/99")
    assert response.status_code == 404
    assert response.get_json()["code"] == "ROOM_NOT_FOUND"


def test_400_errors(client):
    assert client.get("/rooms/abc").status_code == 400
    response = client.post("/rooms", json={"number": "", "price": -100})
    assert response.status_code == 400
    assert response.get_json()["code"] == "VALIDATION_ERROR"
    assert client.post("/rooms", data="not json").status_code == 400
    assert client.get("/rooms?sort=color").status_code == 400


def test_405(client):
    response = client.post("/rooms/1", json=NEW_ROOM)
    assert response.status_code == 405
    assert "error" in response.get_json()


def test_filter_and_sort(client):
    data = client.get("/rooms?min_price=4000&max_price=9500&sort=price&order=desc").get_json()
    assert [r["number"] for r in data] == ["301", "201"]
    data = client.get("/rooms?room_type=standard").get_json()
    assert [r["number"] for r in data] == ["101"]


def test_available_endpoint(client):
    data = client.get("/rooms/available?guests=3").get_json()
    assert [r["number"] for r in data] == ["201"]


def test_statistics(client):
    data = client.get("/rooms/statistics").get_json()
    assert data["rooms_count"] == 3
    assert data["available_count"] == 2
