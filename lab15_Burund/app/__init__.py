"""Лабораторная работа №15. Вариант 5. Ресторан — веб-приложение на Flask.

Запуск: flask --app app run      (заполнить БД: flask --app app seed)
"""

import logging
import time

import click
from flask import Flask, g, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from app.config import Config
from app.database import Database, get_session
from app.services import ServiceError


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)
    logging.basicConfig(level=config.LOG_LEVEL,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("restaurant")

    database = Database(config.DATABASE_URL)
    database.init_app(app)
    database.create_all()

    from app.routes.api import api
    from app.routes.web import web

    app.register_blueprint(web)
    app.register_blueprint(api, url_prefix="/api")

    @app.before_request
    def start_timer():
        g.started = time.perf_counter()

    @app.after_request
    def log_request(response):
        elapsed = (time.perf_counter() - g.get("started", time.perf_counter())) * 1000
        if not request.path.startswith("/static"):
            log.info("%s %s -> %s (%.1f мс)", request.method, request.full_path.rstrip("?"),
                     response.status_code, elapsed)
        return response

    def wants_json() -> bool:
        return request.path.startswith("/api/")

    @app.errorhandler(ServiceError)
    def service_error(error: ServiceError):
        get_session().rollback()
        if wants_json():
            return jsonify({"error": str(error)}), error.status_code
        template = "404.html" if error.status_code == 404 else "error.html"
        return render_template(template, message=str(error),
                               code=error.status_code), error.status_code

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        if wants_json():
            return jsonify({"error": error.description}), error.code
        template = "404.html" if error.code == 404 else "error.html"
        return render_template(template, message=error.description, code=error.code), error.code

    @app.errorhandler(Exception)
    def internal_error(error: Exception):
        log.exception("Внутренняя ошибка сервера")
        get_session().rollback()
        if wants_json():
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500
        return render_template("error.html", message="Внутренняя ошибка сервера", code=500), 500

    @app.cli.command("seed")
    def seed_command():
        """Заполнить базу демонстрационными данными."""
        from app.seed import seed

        with database.session_factory() as session:
            click.echo("Данные добавлены" if seed(session) else "База уже содержит данные")

    log.info("Приложение запущено (%s)", config.FLASK_ENV)
    return app
