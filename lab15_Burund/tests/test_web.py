def test_pages_open(client):
    for url in ("/", "/dishes", "/dishes/1", "/dishes/create", "/dishes/1/edit", "/categories",
                "/categories/1", "/orders", "/orders/1", "/orders/create"):
        response = client.get(url)
        assert response.status_code == 200, url


def test_search_filter_sort(client):
    html = client.get("/dishes?search=салат").get_data(as_text=True)
    assert "Греческий салат" in html and "Борщ" not in html
    html = client.get("/dishes?vegetarian=1&max_price=400").get_data(as_text=True)
    assert "Греческий салат" in html and "Цезарь" not in html
    html = client.get("/dishes?sort=-price").get_data(as_text=True)
    assert html.index("Стейк рибай") < html.index("Морс клюквенный")


def test_create_edit_delete_dish(client):
    response = client.post("/dishes/create", data={
        "name": "Окрошка", "category_id": "2", "price": "320", "weight_g": "300",
        "is_available": "1", "description": "На квасе"}, follow_redirects=True)
    assert "Блюдо «Окрошка» добавлено" in response.get_data(as_text=True)
    response = client.post("/dishes/13/edit", data={
        "name": "Окрошка на кефире", "category_id": "2", "price": "330", "weight_g": "300"},
        follow_redirects=True)
    assert "Окрошка на кефире" in response.get_data(as_text=True)
    response = client.post("/dishes/13/delete", follow_redirects=True)
    assert "Блюдо удалено" in response.get_data(as_text=True)
    assert client.get("/dishes/13").status_code == 404


def test_form_validation_errors(client):
    response = client.post("/dishes/create", data={"name": "", "category_id": "1",
                                                   "price": "-1", "weight_g": "10"})
    assert response.status_code == 200
    assert "обязательно" in response.get_data(as_text=True)
    response = client.post("/dishes/create", data={"name": "Борщ", "category_id": "2",
                                                   "price": "100", "weight_g": "10"})
    assert "уже есть в меню" in response.get_data(as_text=True)


def test_custom_404(client):
    response = client.get("/dishes/999")
    assert response.status_code == 404
    assert "Блюдо #999 не найдено" in response.get_data(as_text=True)
    assert client.get("/no-such-page").status_code == 404


def test_order_via_form(client):
    response = client.post("/orders/create", data={
        "customer_name": "Бурунд", "table_number": "4", "qty_1": "2", "qty_11": "1"},
        follow_redirects=True)
    html = response.get_data(as_text=True)
    assert "оформлен на сумму 1090.00" in html
    response = client.post("/orders/4/status", data={"status": "cooking"}, follow_redirects=True)
    assert "Статус заказа: готовится" in response.get_data(as_text=True)


def test_delete_dish_in_order_is_conflict(client):
    response = client.post("/dishes/1/delete", follow_redirects=True)
    assert "есть в заказах" in response.get_data(as_text=True)
