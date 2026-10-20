from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.database import get_session
from app.models import OrderStatus
from app.routes.forms import dish_filters, order_items_from_form
from app.services import CategoryService, DishService, OrderService, ServiceError

web = Blueprint("web", __name__)

SORT_OPTIONS = {"name": "по названию", "price": "сначала дешёвые", "-price": "сначала дорогие",
                "weight": "по весу порции"}


def services():
    session = get_session()
    return CategoryService(session), DishService(session), OrderService(session)


@web.get("/")
def index():
    categories, dishes, orders = services()
    return render_template("index.html", categories=categories.list_all(),
                           popular=dishes.popular(), orders=orders.list_all()[:5])


# --- блюда ---
@web.get("/dishes")
def dish_list():
    categories, dishes, _ = services()
    filters, sort = dish_filters()
    return render_template("dishes/list.html", dishes=dishes.list_all(filters, sort),
                           categories=categories.list_all(), filters=filters, sort=sort,
                           sort_options=SORT_OPTIONS)


@web.get("/dishes/<int:dish_id>")
def dish_detail(dish_id: int):
    _, dishes, _ = services()
    return render_template("dishes/detail.html", dish=dishes.get(dish_id))


@web.route("/dishes/create", methods=["GET", "POST"])
def dish_create():
    categories, dishes, _ = services()
    if request.method == "POST":
        try:
            dish = dishes.create(request.form.to_dict())
        except ServiceError as error:
            get_session().rollback()
            flash(str(error), "error")
        else:
            flash(f"Блюдо «{dish.name}» добавлено в меню", "success")
            return redirect(url_for("web.dish_detail", dish_id=dish.id))
    return render_template("dishes/form.html", dish=None, form=request.form,
                           categories=categories.list_all())


@web.route("/dishes/<int:dish_id>/edit", methods=["GET", "POST"])
def dish_edit(dish_id: int):
    categories, dishes, _ = services()
    dish = dishes.get(dish_id)
    if request.method == "POST":
        try:
            dishes.update(dish_id, request.form.to_dict())
        except ServiceError as error:
            get_session().rollback()
            flash(str(error), "error")
        else:
            flash("Изменения сохранены", "success")
            return redirect(url_for("web.dish_detail", dish_id=dish_id))
    return render_template("dishes/form.html", dish=dish, form=request.form,
                           categories=categories.list_all())


@web.post("/dishes/<int:dish_id>/delete")
def dish_delete(dish_id: int):
    _, dishes, _ = services()
    try:
        dishes.delete(dish_id)
    except ServiceError as error:
        get_session().rollback()
        flash(str(error), "error")
        return redirect(url_for("web.dish_detail", dish_id=dish_id))
    flash("Блюдо удалено", "success")
    return redirect(url_for("web.dish_list"))


# --- категории ---
@web.get("/categories")
def category_list():
    categories, _, _ = services()
    return render_template("categories/list.html", categories=categories.list_all())


@web.get("/categories/<int:category_id>")
def category_detail(category_id: int):
    categories, _, _ = services()
    return render_template("categories/detail.html", category=categories.get(category_id))


@web.post("/categories")
def category_create():
    categories, _, _ = services()
    try:
        categories.create(request.form.to_dict())
        flash("Категория добавлена", "success")
    except ServiceError as error:
        get_session().rollback()
        flash(str(error), "error")
    return redirect(url_for("web.category_list"))


@web.post("/categories/<int:category_id>/delete")
def category_delete(category_id: int):
    categories, _, _ = services()
    try:
        categories.delete(category_id)
        flash("Категория удалена", "success")
    except ServiceError as error:
        get_session().rollback()
        flash(str(error), "error")
    return redirect(url_for("web.category_list"))


# --- заказы ---
@web.get("/orders")
def order_list():
    _, _, orders = services()
    status = request.args.get("status") or None
    search = request.args.get("search", "").strip()
    return render_template("orders/list.html", orders=orders.list_all(status, search),
                           statuses=list(OrderStatus), status=status, search=search)


@web.route("/orders/create", methods=["GET", "POST"])
def order_create():
    categories, dishes, orders = services()
    if request.method == "POST":
        try:
            order = orders.create(request.form.get("customer_name", ""),
                                  request.form.get("table_number"), order_items_from_form(),
                                  request.form.get("comment", ""))
        except ServiceError as error:
            get_session().rollback()
            flash(str(error), "error")
        else:
            flash(f"Заказ #{order.id} оформлен на сумму {order.total:.2f} ₽", "success")
            return redirect(url_for("web.order_detail", order_id=order.id))
    preselected = request.args.get("dish", type=int)
    return render_template("orders/create.html", categories=categories.list_all(),
                           dishes=dishes.list_all({"available": True}), form=request.form,
                           preselected=preselected)


@web.get("/orders/<int:order_id>")
def order_detail(order_id: int):
    _, _, orders = services()
    order = orders.get(order_id)
    return render_template("orders/detail.html", order=order,
                           next_statuses=orders.next_statuses(order))


@web.post("/orders/<int:order_id>/status")
def order_status(order_id: int):
    _, _, orders = services()
    try:
        order = orders.change_status(order_id, request.form.get("status", ""))
        flash(f"Статус заказа: {order.status.value}", "success")
    except ServiceError as error:
        get_session().rollback()
        flash(str(error), "error")
    return redirect(url_for("web.order_detail", order_id=order_id))
