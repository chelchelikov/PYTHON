"""Классы предметной области."""

from exceptions import InvalidMovieDataError, InvalidRatingError

MIN_RATING = 0.0
MAX_RATING = 10.0
MIN_YEAR = 1888
MAX_YEAR = 2100


class Movie:
    def __init__(self, movie_id, title, genre, year, rating):
        self.movie_id = movie_id
        self.title = title
        self.genre = genre
        self.year = year
        self.rating = rating

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        if not isinstance(value, str) or not value.strip():
            raise InvalidMovieDataError("Название не может быть пустым")
        self._title = value.strip()

    @property
    def genre(self):
        return self._genre

    @genre.setter
    def genre(self, value):
        if not isinstance(value, str) or not value.strip():
            raise InvalidMovieDataError("Жанр не может быть пустым")
        self._genre = value.strip().lower()

    @property
    def year(self):
        return self._year

    @year.setter
    def year(self, value):
        if not isinstance(value, int) or not MIN_YEAR <= value <= MAX_YEAR:
            raise InvalidMovieDataError(
                f"Год должен быть целым числом от {MIN_YEAR} до {MAX_YEAR}")
        self._year = value

    @property
    def rating(self):
        return self._rating

    @rating.setter
    def rating(self, value):
        if not isinstance(value, (int, float)) or not MIN_RATING <= value <= MAX_RATING:
            raise InvalidRatingError(value)
        self._rating = float(value)

    def to_dict(self):
        return {
            "id": self.movie_id,
            "title": self.title,
            "genre": self.genre,
            "year": self.year,
            "rating": self.rating,
        }

    @classmethod
    def from_dict(cls, data):
        try:
            return cls(int(data["id"]), data["title"], data["genre"],
                       int(data["year"]), float(data["rating"]))
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidMovieDataError(f"Некорректная запись фильма: {data}") from error

    def __str__(self):
        return (f"#{self.movie_id:<3} {self.title:<25} {self.genre:<12} "
                f"{self.year:<5} {self.rating:.1f}")
