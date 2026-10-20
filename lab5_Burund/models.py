"""Классы предметной области: фильмы."""


class Movie:
    kind = "Фильм"

    def __init__(self, title, genre, year, rating, duration):
        if not title:
            raise ValueError("Название не может быть пустым")
        if not 0 <= rating <= 10:
            raise ValueError(f"Некорректный рейтинг «{title}»: {rating}")
        if duration <= 0:
            raise ValueError(f"Некорректная продолжительность «{title}»: {duration}")
        self.title = title
        self.genre = genre
        self.year = year
        self.rating = rating
        self.duration = duration  # минуты

    def duration_text(self):
        hours, minutes = divmod(self.duration, 60)
        return f"{hours} ч {minutes:02d} мин"

    def __str__(self):
        return (f"{self.kind:<14} {self.title:<26} {self.genre:<11} {self.year}  "
                f"★{self.rating:<4} {self.duration_text()}")


class FeatureFilm(Movie):
    kind = "Художественный"

    def __init__(self, title, genre, year, rating, duration, director):
        super().__init__(title, genre, year, rating, duration)
        self.director = director


class AnimatedFilm(Movie):
    kind = "Мультфильм"

    def __init__(self, title, genre, year, rating, duration, studio):
        super().__init__(title, genre, year, rating, duration)
        self.studio = studio


class Documentary(Movie):
    kind = "Документальный"

    def __init__(self, title, genre, year, rating, duration, topic):
        super().__init__(title, genre, year, rating, duration)
        self.topic = topic
