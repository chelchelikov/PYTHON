"""Генераторы и итераторы."""


def movies_of_year(movies, year):
    for movie in movies:
        if movie.year == year:
            yield movie


class DurationIterator:
    """Итератор по фильмам, которые суммарно укладываются в заданное время просмотра."""

    def __init__(self, movies, time_limit):
        self._movies = sorted(movies, key=lambda movie: movie.duration)
        self._time_left = time_limit
        self._index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._index >= len(self._movies):
            raise StopIteration
        movie = self._movies[self._index]
        if movie.duration > self._time_left:
            raise StopIteration
        self._index += 1
        self._time_left -= movie.duration
        return movie
