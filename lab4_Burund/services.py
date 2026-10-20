"""Бизнес-логика каталога фильмов."""

from exceptions import MovieNotFoundError
from models import Movie

SORT_FIELDS = {
    "title": "названию",
    "year": "году",
    "rating": "рейтингу",
}


class MovieCatalog:
    def __init__(self, movies=None):
        self.movies = list(movies) if movies else []

    def _next_id(self):
        return max((movie.movie_id for movie in self.movies), default=0) + 1

    def add(self, title, genre, year, rating):
        movie = Movie(self._next_id(), title, genre, year, rating)
        self.movies.append(movie)
        return movie

    def get(self, movie_id):
        for movie in self.movies:
            if movie.movie_id == movie_id:
                return movie
        raise MovieNotFoundError(movie_id)

    def remove(self, movie_id):
        movie = self.get(movie_id)
        self.movies.remove(movie)
        return movie

    def update(self, movie_id, **fields):
        movie = self.get(movie_id)
        # Проверяем все значения на копии, чтобы не изменить объект частично
        candidate = Movie.from_dict({**movie.to_dict(), **fields})
        movie.title = candidate.title
        movie.genre = candidate.genre
        movie.year = candidate.year
        movie.rating = candidate.rating
        return movie

    def search(self, text):
        text = text.lower()
        return [m for m in self.movies if text in m.title.lower() or text == m.genre]

    def filter_by_rating(self, min_rating, max_rating=10.0):
        return [m for m in self.movies if min_rating <= m.rating <= max_rating]

    def sort(self, field="rating", descending=True):
        if field not in SORT_FIELDS:
            raise ValueError(f"Неизвестное поле сортировки: {field}")
        return sorted(self.movies, key=lambda m: getattr(m, field), reverse=descending)

    def rating_statistics(self):
        if not self.movies:
            return None
        ratings = [m.rating for m in self.movies]
        best = max(self.movies, key=lambda m: m.rating)
        worst = min(self.movies, key=lambda m: m.rating)
        by_genre = {}
        for movie in self.movies:
            by_genre.setdefault(movie.genre, []).append(movie.rating)
        return {
            "count": len(ratings),
            "average": sum(ratings) / len(ratings),
            "best": best,
            "worst": worst,
            "genre_average": {g: sum(r) / len(r) for g, r in by_genre.items()},
        }
