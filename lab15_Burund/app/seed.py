"""Демонстрационные данные: flask --app app seed"""

from sqlalchemy.orm import Session

from app.models import Category, Dish, Order, OrderItem, OrderStatus

CATEGORIES = {
    "Салаты": "Свежие салаты из сезонных овощей",
    "Супы": "Горячие супы по домашним рецептам",
    "Горячее": "Основные блюда из мяса, рыбы и птицы",
    "Десерты": "Сладкое к чаю и кофе",
    "Напитки": "Морсы, лимонады и чай",
}

DISHES = [
    ("Цезарь с курицей", "Салаты", 450, 250, False, "Романо, курица гриль, пармезан, соус цезарь"),
    ("Греческий салат", "Салаты", 390, 230, True, "Томаты, огурцы, фета, маслины"),
    ("Борщ", "Супы", 350, 300, False, "Со сметаной и чесночными пампушками"),
    ("Грибной крем-суп", "Супы", 380, 300, True, "Шампиньоны, сливки, гренки"),
    ("Стейк рибай", "Горячее", 1890, 300, False, "Мраморная говядина, соус демиглас"),
    ("Паста карбонара", "Горячее", 590, 320, False, "Спагетти, гуанчале, желток, пекорино"),
    ("Лосось на гриле", "Горячее", 1250, 250, False, "С овощами и лимонным соусом"),
    ("Овощное рагу", "Горячее", 420, 300, True, "Кабачки, баклажаны, перец, томаты"),
    ("Чизкейк", "Десерты", 380, 150, True, "Классический нью-йоркский"),
    ("Тирамису", "Десерты", 420, 140, True, "Маскарпоне, савоярди, эспрессо"),
    ("Морс клюквенный", "Напитки", 190, 400, True, "Домашний, без сахара"),
    ("Лимонад имбирный", "Напитки", 250, 400, True, "Имбирь, лайм, мята"),
]


def seed(session: Session) -> bool:
    if session.query(Category).count():
        return False
    categories = {name: Category(name=name, description=text) for name, text in CATEGORIES.items()}
    session.add_all(categories.values())
    dishes = {}
    for name, category, price, weight, vegetarian, description in DISHES:
        dishes[name] = Dish(name=name, category=categories[category], price=price,
                            weight_g=weight, is_vegetarian=vegetarian, description=description)
    dishes["Тирамису"].is_available = False
    session.add_all(dishes.values())

    def order(customer, table, status, items):
        session.add(Order(customer_name=customer, table_number=table, status=status,
                          items=[OrderItem(dish=dishes[n], quantity=q, price=dishes[n].price)
                                 for n, q in items]))

    order("Иванов Иван", 3, OrderStatus.PAID, [("Цезарь с курицей", 1), ("Стейк рибай", 1),
                                               ("Морс клюквенный", 2)])
    order("Петрова Анна", 5, OrderStatus.COOKING, [("Борщ", 2), ("Чизкейк", 2)])
    order("Бурунд", 1, OrderStatus.NEW, [("Паста карбонара", 1), ("Греческий салат", 1),
                                         ("Лимонад имбирный", 1)])
    session.commit()
    return True
