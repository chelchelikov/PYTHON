"""Пользовательские исключения каталога фильмов."""


class CatalogError(Exception):
    """Базовое исключение каталога."""


class InvalidRatingError(CatalogError):
    def __init__(self, rating):
        super().__init__(f"Некорректный рейтинг: {rating}. Допустимо от 0 до 10")
        self.rating = rating


class InvalidMovieDataError(CatalogError):
    pass


class MovieNotFoundError(CatalogError):
    def __init__(self, movie_id):
        super().__init__(f"Фильм с id={movie_id} не найден")
        self.movie_id = movie_id


class StorageError(CatalogError):
    pass
