NEW_ROOM = {"number": "501", "room_type": "suite", "floor": 5, "capacity": 4, "price": 15000,
            "amenities": ["WiFi", "Jacuzzi", "wifi"]}


def test_list(client):
    data = client.get("/rooms").json()
    assert data["total"] == 12
    assert len(data["items"]) == 10  # limit по умолчанию


def test_get_existing_and_missing(client):
    assert client.get("/rooms/1").json()["number"] == "101"
    response = client.get("/rooms/999")
    assert response.status_code == 404
    assert "не найден" in response.json()["detail"]


def test_post_valid(client):
    response = client.post("/rooms", json=NEW_ROOM)
    assert response.status_code == 201
    body = response.json()
    assert body["amenities"] == ["jacuzzi", "wifi"]
    assert response.headers["Location"] == f"/rooms/{body['id']}"


def test_post_invalid(client):
    response = client.post("/rooms", json={**NEW_ROOM, "price": -5, "room_type": "palace"})
    assert response.status_code == 422
    fields = {e["field"] for e in response.json()["errors"]}
    assert {"price", "room_type"} <= fields


def test_post_missing_fields_and_duplicate(client):
    assert client.post("/rooms", json={"number": "777"}).status_code == 422
    assert client.post("/rooms", json={**NEW_ROOM, "number": "101"}).status_code == 409


def test_put(client):
    response = client.put("/rooms/1", json={**NEW_ROOM, "number": "101", "price": 4000})
    assert response.status_code == 200
    assert response.json()["room_type"] == "suite"
    assert response.json()["price"] == 4000


def test_patch_keeps_other_fields(client):
    response = client.patch("/rooms/4", json={"price": 5900})
    assert response.status_code == 200
    body = response.json()
    assert body["price"] == 5900
    assert body["number"] == "201" and body["room_type"] == "deluxe"


def test_delete_and_repeat(client):
    assert client.delete("/rooms/3").status_code == 204
    assert client.get("/rooms/3").status_code == 404
    assert client.delete("/rooms/3").status_code == 404


def test_filter(client):
    data = client.get("/rooms", params={"type": "suite", "min_price": 9000}).json()
    assert [r["number"] for r in data["items"]] == ["301", "401"]
    data = client.get("/rooms", params={"max_price": 3500, "is_available": True}).json()
    assert [r["number"] for r in data["items"]] == ["101", "103"]


def test_sort(client):
    data = client.get("/rooms", params={"sort": "price", "order": "desc", "limit": 3}).json()
    assert [r["price"] for r in data["items"]] == [12000, 9000, 8500]


def test_pagination(client):
    first = client.get("/rooms", params={"limit": 5, "offset": 0}).json()
    third = client.get("/rooms", params={"limit": 5, "offset": 10}).json()
    assert len(first["items"]) == 5 and len(third["items"]) == 2
    assert first["total"] == third["total"] == 12


def test_search(client):
    numbers = [r["number"] for r in client.get("/rooms/search", params={"q": "jacuzzi"}).json()]
    assert numbers == ["401"]
    assert len(client.get("/rooms/search", params={"q": "family"}).json()) == 2


def test_statistics(client):
    stats = client.get("/rooms/statistics").json()
    assert stats["total"] == 12
    assert stats["available"] == 9
    assert stats["max_price"] == 12000
    assert stats["occupancy_percent"] == 25.0
    assert {t["room_type"] for t in stats["by_type"]} == {"standard", "deluxe", "suite", "family"}


def test_validation_of_query_params(client):
    assert client.get("/rooms", params={"limit": 0}).status_code == 422
    assert client.get("/rooms", params={"sort": "color"}).status_code == 422
    assert client.get("/rooms/abc").status_code == 422
    assert client.patch("/rooms/1", json={"capacity": 0}).status_code == 422


def test_cache_miss_hit_and_invalidation(client):
    assert client.get("/rooms/2").headers["X-Cache"] == "MISS"
    assert client.get("/rooms/2").headers["X-Cache"] == "HIT"
    client.patch("/rooms/2", json={"is_available": True})
    response = client.get("/rooms/2")
    assert response.headers["X-Cache"] == "MISS"
    assert response.json()["is_available"] is True
    assert client.get("/rooms/2").headers["X-Cache"] == "HIT"


def test_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/rooms", "/rooms/{room_id}", "/rooms/search", "/rooms/statistics"} <= set(paths)
