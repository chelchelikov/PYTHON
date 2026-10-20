"""Функции обработки коллекций (функции высшего порядка)."""

from functools import reduce


def filter_objects(objects, predicate):
    return filter(predicate, objects)


def transform_objects(objects, operation):
    return map(operation, objects)


def sort_objects(objects, key_function, reverse=False):
    return sorted(objects, key=key_function, reverse=reverse)


def min_rating(threshold):
    """Возвращает предикат «рейтинг не ниже threshold» (функция, возвращающая функцию)."""
    return lambda movie: movie.rating >= threshold


def get_titles(movies):
    return list(map(lambda movie: movie.title, movies))


def average_duration(movies):
    movies = list(movies)
    if not movies:
        raise ValueError("Нет фильмов для расчёта")
    total = reduce(lambda acc, movie: acc + movie.duration, movies, 0)
    return total / len(movies)


def has_genre(movies, genre):
    return any(movie.genre == genre for movie in movies)


def all_rated_above(movies, threshold):
    return all(movie.rating > threshold for movie in movies)


def count_by_genre(movies):
    genres = {movie.genre for movie in movies}
    return {genre: sum(1 for m in movies if m.genre == genre) for genre in sorted(genres)}


def process(objects, predicate, transform, key_function, reverse=False):
    """Конвейер: filter -> sorted -> map, результат отдаётся лениво."""
    selected = filter(predicate, objects)
    for item in sorted(selected, key=key_function, reverse=reverse):
        yield transform(item)
