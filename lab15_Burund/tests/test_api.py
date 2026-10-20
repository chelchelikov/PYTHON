NEW_DISH = {"name": "Солянка", "category_id": 2, "price": 420, "weight_g": 300,
            "is_available": True, "description": "Сборная мясная"}


def test_list_and_filters(client):
    assert len(client.get("/api/dishes").get_json()) == 12
    data = client.get("/api/dishes?category=5&sort=price").get_json()
    assert [d["name"] for d in data] == ["Морс клюквенный", "Лимонад имбирный"]


def test_crud(client):
    response = client.post("/api/dishes", json=NEW_DISH)
    assert response.status_code == 201
    dish_id = response.get_json()["id"]
    assert client.patch(f"/api/dishes/{dish_id}", json={"price": 450}).get_json()["price"] == 450
    replaced = client.put(f"/api/dishes/{dish_id}", json={**NEW_DISH, "name": "Солянка сборная"})
    assert replaced.get_json()["name"] == "Солянка сборная"
    assert client.delete(f"/api/dishes/{dish_id}").status_code == 204
    assert client.get(f"/api/dishes/{dish_id}").status_code == 404


def test_api_errors(client):
    assert client.post("/api/dishes", json={**NEW_DISH, "price": "abc"}).status_code == 400
    assert client.post("/api/dishes", json={**NEW_DISH, "name": "Борщ"}).status_code == 409
    assert client.post("/api/dishes", data="text").status_code == 400
    assert client.post("/api/dishes", json={**NEW_DISH, "category_id": 99}).status_code == 400
    assert client.get("/api/orders/999").get_json() == {"error": "Заказ #999 не найден"}


def test_order_api(client):
    response = client.post("/api/orders", json={
        "customer_name": "Гость", "table_number": 2,
        "items": [{"dish_id": 5, "quantity": 1}, {"dish_id": 9, "quantity": 2}]})
    assert response.status_code == 201
    order = response.get_json()
    assert order["total"] == 1890 + 380 * 2
    assert client.patch(f"/api/orders/{order['id']}", json={"status": "paid"}).status_code == 409
    response = client.patch(f"/api/orders/{order['id']}", json={"status": "cancelled"})
    assert response.get_json()["status"] == "cancelled"


def test_unavailable_dish_and_related(client):
    response = client.post("/api/orders", json={"customer_name": "Гость", "table_number": 2,
                                                "items": [{"dish_id": 10, "quantity": 1}]})
    assert response.status_code == 409  # тирамису нет в наличии
    dishes = client.get("/api/categories/4/dishes").get_json()
    assert {d["name"] for d in dishes} == {"Чизкейк", "Тирамису"}
