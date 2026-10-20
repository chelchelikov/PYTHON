"""Лабораторная работа №4. Вариант 5. Каталог фильмов."""

from exceptions import CatalogError, StorageError
from services import SORT_FIELDS, MovieCatalog
from storage import CSV_PATH, JSON_PATH, export_csv, load_json, save_json


def read_int(prompt):
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            print("Ошибка: необходимо ввести целое число")


def read_float(prompt):
    while True:
        try:
            return float(input(prompt).replace(",", "."))
        except ValueError:
            print("Ошибка: необходимо ввести число")


def print_movies(movies):
    if not movies:
        print("Фильмы не найдены")
        return
    print(f"{'id':<4} {'Название':<25} {'Жанр':<12} {'Год':<5} Рейтинг")
    for movie in movies:
        print(movie)


def add_movie(catalog):
    title = input("Название: ")
    genre = input("Жанр: ")
    year = read_int("Год: ")
    rating = read_float("Рейтинг (0-10): ")
    movie = catalog.add(title, genre, year, rating)
    print(f"Добавлен фильм #{movie.movie_id}")


def edit_movie(catalog):
    movie = catalog.get(read_int("id фильма: "))
    print("Текущие данные:", movie)
    print("Оставьте поле пустым, чтобы не менять его")
    fields = {}
    for key, label in (("title", "Название"), ("genre", "Жанр"),
                       ("year", "Год"), ("rating", "Рейтинг")):
        value = input(f"{label}: ").strip()
        if value:
            fields[key] = value.replace(",", ".") if key == "rating" else value
    catalog.update(movie.movie_id, **fields)
    print("Изменено:", movie)


def sort_movies(catalog):
    for key, label in SORT_FIELDS.items():
        print(f"  {key} — по {label}")
    field = input("Поле: ").strip() or "rating"
    descending = input("По убыванию? (д/н): ").strip().lower() != "н"
    print_movies(catalog.sort(field, descending))


def show_statistics(catalog):
    stats = catalog.rating_statistics()
    if stats is None:
        print("Каталог пуст")
        return
    print(f"Фильмов: {stats['count']}")
    print(f"Средний рейтинг: {stats['average']:.2f}")
    print(f"Лучший: {stats['best'].title} ({stats['best'].rating})")
    print(f"Худший: {stats['worst'].title} ({stats['worst'].rating})")
    print("Средний рейтинг по жанрам:")
    for genre, average in stats["genre_average"].items():
        print(f"  {genre}: {average:.2f}")


MENU = """
===== КАТАЛОГ ФИЛЬМОВ =====
1. Добавить фильм
2. Показать все фильмы
3. Поиск (по названию или жанру)
4. Фильтрация по рейтингу
5. Сортировка
6. Статистика рейтингов
7. Изменить фильм
8. Удалить фильм
9. Сохранить в JSON
10. Экспортировать в CSV
11. Загрузить из JSON
0. Выход"""


def main():
    try:
        catalog = MovieCatalog(load_json())
        print(f"Загружено фильмов: {len(catalog.movies)}")
    except StorageError as error:
        print("Ошибка загрузки:", error)
        print("Запуск с пустым каталогом")
        catalog = MovieCatalog()

    while True:
        print(MENU)
        choice = input("Выберите действие: ").strip()
        try:
            if choice == "1":
                add_movie(catalog)
            elif choice == "2":
                print_movies(catalog.movies)
            elif choice == "3":
                print_movies(catalog.search(input("Строка поиска: ")))
            elif choice == "4":
                print_movies(catalog.filter_by_rating(read_float("Минимальный рейтинг: ")))
            elif choice == "5":
                sort_movies(catalog)
            elif choice == "6":
                show_statistics(catalog)
            elif choice == "7":
                edit_movie(catalog)
            elif choice == "8":
                movie = catalog.remove(read_int("id фильма: "))
                print(f"Удалён фильм «{movie.title}»")
            elif choice == "9":
                save_json(catalog.movies)
                print(f"Сохранено в {JSON_PATH}")
            elif choice == "10":
                export_csv(catalog.movies)
                print(f"Экспортировано в {CSV_PATH}")
            elif choice == "11":
                catalog = MovieCatalog(load_json())
                print(f"Загружено фильмов: {len(catalog.movies)}")
            elif choice == "0":
                if input("Сохранить данные перед выходом? (д/н): ").strip().lower() != "н":
                    save_json(catalog.movies)
                    print("Данные сохранены")
                print("До свидания!")
                break
            else:
                print("Ошибка: неизвестный пункт меню")
        except CatalogError as error:
            print("Ошибка:", error)
        except ValueError as error:
            print("Ошибка:", error)


if __name__ == "__main__":
    main()
