"""Лабораторная работа №5. Вариант 5. Фильмы."""

from generators import DurationIterator, movies_of_year
from models import AnimatedFilm, Documentary, FeatureFilm
from operations import (all_rated_above, average_duration, count_by_genre,
                        filter_objects, get_titles, has_genre, min_rating,
                        process, sort_objects, transform_objects)


def create_movies():
    return [
        FeatureFilm("Интерстеллар", "фантастика", 2014, 8.6, 169, "К. Нолан"),
        FeatureFilm("Начало", "фантастика", 2010, 8.7, 148, "К. Нолан"),
        FeatureFilm("Зелёная миля", "драма", 1999, 9.1, 189, "Ф. Дарабонт"),
        FeatureFilm("Остров проклятых", "триллер", 2010, 8.5, 138, "М. Скорсезе"),
        AnimatedFilm("Тайна Коко", "мультфильм", 2017, 8.7, 105, "Pixar"),
        AnimatedFilm("Унесённые призраками", "мультфильм", 2001, 8.6, 125, "Ghibli"),
        AnimatedFilm("Холодное сердце", "мультфильм", 2013, 7.4, 102, "Disney"),
        Documentary("Наша планета", "природа", 2019, 9.0, 50, "экология"),
        Documentary("Ганс Циммер", "музыка", 2017, 8.1, 90, "музыка"),
    ]


def print_movies(movies):
    for movie in movies:
        print(" ", movie)


def read_number(prompt, number_type=float):
    while True:
        try:
            return number_type(input(prompt).replace(",", "."))
        except ValueError:
            print("Ошибка: необходимо ввести число")


def show_filter(movies):
    threshold = read_number("Минимальный рейтинг: ")
    result = list(filter_objects(movies, min_rating(threshold)))
    print(f"Фильмы с рейтингом от {threshold}:")
    if result:
        print_movies(result)
    else:
        print("  нет")


def show_titles(movies):
    print("Названия (map):", ", ".join(get_titles(movies)))
    durations = transform_objects(movies, lambda m: f"{m.title} — {m.duration_text()}")
    for line in durations:
        print(" ", line)


def show_sorted(movies):
    descending = input("По убыванию? (д/н): ").strip().lower() == "д"
    print_movies(sort_objects(movies, lambda m: m.duration, descending))


def show_statistics(movies):
    print(f"Средняя продолжительность: {average_duration(movies):.1f} мин")
    print("Количество по жанрам:", count_by_genre(movies))
    longest = max(movies, key=lambda m: m.duration)
    print(f"Самый длинный: {longest.title} ({longest.duration_text()})")


def run_generator(movies):
    year = read_number("Год: ", int)
    generator = movies_of_year(movies, year)
    print("Первые фильмы через next():")
    for _ in range(2):
        movie = next(generator, None)
        if movie is None:
            print("  больше фильмов нет")
            return
        print(" ", movie)
    print("Остальные:")
    remaining = list(generator)
    if remaining:
        print_movies(remaining)
    else:
        print("  нет")
    try:
        next(generator)
    except StopIteration:
        print("Генератор исчерпан (StopIteration)")


def run_iterator(movies):
    limit = read_number("Свободное время, мин: ", int)
    plan = list(DurationIterator(movies, limit))
    print(f"Успеете посмотреть {len(plan)} фильм(ов):")
    print_movies(plan)


def check_conditions(movies):
    genre = input("Жанр для проверки: ").strip().lower()
    print(f"Есть фильмы жанра «{genre}» (any): {'да' if has_genre(movies, genre) else 'нет'}")
    print(f"У всех рейтинг выше 7 (all): {'да' if all_rated_above(movies, 7) else 'нет'}")


def run_pipeline(movies):
    print("Конвейер 1: мультфильмы по рейтингу")
    for line in process(movies, lambda m: m.genre == "мультфильм",
                        lambda m: f"{m.title}: {m.rating}", lambda m: m.rating, True):
        print(" ", line)
    print("Конвейер 2: фильмы короче 2 часов по году")
    for line in process(movies, lambda m: m.duration < 120,
                        lambda m: f"{m.year} {m.title}", lambda m: m.year):
        print(" ", line)


MENU = """
===== МЕНЮ =====
1. Показать все фильмы
2. Фильтрация по рейтингу (filter)
3. Названия и продолжительность (map)
4. Сортировка по продолжительности (sorted)
5. Статистика (reduce, comprehension)
6. Генератор фильмов заданного года
7. Итератор: что успеть посмотреть
8. Проверка условий (any/all)
9. Конвейер обработки
0. Выход"""


def main():
    try:
        movies = create_movies()
    except ValueError as error:
        print("Ошибка в исходных данных:", error)
        return

    actions = {
        "1": print_movies, "2": show_filter, "3": show_titles,
        "4": show_sorted, "5": show_statistics, "6": run_generator,
        "7": run_iterator, "8": check_conditions, "9": run_pipeline,
    }
    while True:
        print(MENU)
        choice = input("Выберите действие: ").strip()
        if choice == "0":
            break
        action = actions.get(choice)
        if action is None:
            print("Ошибка: неизвестный пункт меню")
            continue
        try:
            action(movies)
        except ValueError as error:
            print("Ошибка:", error)


if __name__ == "__main__":
    main()
