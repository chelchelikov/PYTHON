"""Сохранение и загрузка данных."""

import csv
import json
import os

from exceptions import CatalogError, StorageError
from models import Movie

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
JSON_PATH = os.path.join(DATA_DIR, "data.json")
CSV_PATH = os.path.join(DATA_DIR, "data.csv")


def load_json(path=JSON_PATH):
    """Загружает фильмы из JSON. Если файла нет, возвращает пустой список."""
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as error:
        raise StorageError(f"Файл {path} повреждён: {error}") from error

    if not isinstance(data, list):
        raise StorageError(f"Файл {path} должен содержать список фильмов")
    try:
        return [Movie.from_dict(item) for item in data]
    except CatalogError as error:
        raise StorageError(str(error)) from error


def save_json(movies, path=JSON_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump([movie.to_dict() for movie in movies], file,
                      ensure_ascii=False, indent=4)
    except OSError as error:
        raise StorageError(f"Не удалось сохранить {path}: {error}") from error


def export_csv(movies, path=CSV_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["id", "title", "genre", "year", "rating"])
            writer.writeheader()
            for movie in movies:
                writer.writerow(movie.to_dict())
    except OSError as error:
        raise StorageError(f"Не удалось экспортировать {path}: {error}") from error
