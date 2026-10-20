"""Лабораторная работа №2. Вариант 5. Фильмы."""

MIN_YEAR = 1888
MAX_YEAR = 2100
MIN_RATING = 0.0
MAX_RATING = 10.0


def read_text(prompt):
    while True:
        text = input(prompt).strip()
        if text:
            return text
        print("Ошибка: значение не может быть пустым")


def read_int(prompt, min_value, max_value):
    while True:
        text = input(prompt).strip()
        if not text.isdigit():
            print("Ошибка: необходимо ввести целое положительное число")
            continue
        value = int(text)
        if value < min_value or value > max_value:
            print(f"Ошибка: значение должно быть от {min_value} до {max_value}")
            continue
        return value


def read_float(prompt, min_value, max_value):
    while True:
        text = input(prompt).strip().replace(",", ".")
        try:
            value = float(text)
        except ValueError:
            print("Ошибка: необходимо ввести число")
            continue
        if value < min_value or value > max_value:
            print(f"Ошибка: значение должно быть от {min_value} до {max_value}")
            continue
        return value


def create_movie(title, genre, year, rating):
    return {"title": title, "genre": genre, "year": year, "rating": rating}


def input_movie():
    title = read_text("Название: ")
    genre = read_text("Жанр: ")
    year = read_int("Год выпуска: ", MIN_YEAR, MAX_YEAR)
    rating = read_float("Рейтинг (0-10): ", MIN_RATING, MAX_RATING)
    return create_movie(title, genre, year, rating)


def format_movie(movie):
    return (f"{movie['title']:<25} | {movie['genre']:<12} | "
            f"{movie['year']:<4} | {movie['rating']:.1f}")


def print_movies(movies):
    if not movies:
        print("Список пуст")
        return
    print(f"{'Название':<25} | {'Жанр':<12} | {'Год':<4} | Рейтинг")
    print("-" * 56)
    for movie in movies:
        print(format_movie(movie))


def find_by_genre(movies, genre):
    genre = genre.lower()
    return [movie for movie in movies if movie["genre"].lower() == genre]


def filter_by_rating(movies, min_rating):
    return [movie for movie in movies if movie["rating"] >= min_rating]


def calculate_average_rating(movies):
    total = 0
    for movie in movies:
        total += movie["rating"]
    return total / len(movies)


def find_best_movie(movies):
    best = movies[0]
    for movie in movies:
        if movie["rating"] > best["rating"]:
            best = movie
    return best


def get_unique_genres(movies):
    return {movie["genre"] for movie in movies}


def count_by_genre(movies):
    counts = {}
    for movie in movies:
        counts[movie["genre"]] = counts.get(movie["genre"], 0) + 1
    return counts


def year_range(movies):
    years = [movie["year"] for movie in movies]
    return min(years), max(years)


def sort_movies(movies, field="rating", descending=True):
    return sorted(movies, key=lambda movie: movie[field], reverse=descending)


def show_statistics(movies):
    best = find_best_movie(movies)
    oldest, newest = year_range(movies)
    print(f"Количество фильмов: {len(movies)}")
    print(f"Средний рейтинг: {calculate_average_rating(movies):.2f}")
    print(f"Фильм с максимальным рейтингом: {best['title']} ({best['rating']:.1f})")
    print(f"Годы выпуска: с {oldest} по {newest}")
    print("Количество фильмов по жанрам:")
    for genre, count in count_by_genre(movies).items():
        print(f"  {genre}: {count}")


def demo_movies():
    return [
        create_movie("Интерстеллар", "фантастика", 2014, 8.6),
        create_movie("Начало", "фантастика", 2010, 8.7),
        create_movie("Зелёная миля", "драма", 1999, 9.1),
        create_movie("Остров проклятых", "триллер", 2010, 8.5),
        create_movie("Довод", "фантастика", 2020, 7.4),
        create_movie("Достать ножи", "детектив", 2019, 7.9),
    ]


def print_menu():
    print("\n===== МЕНЮ =====")
    print("1. Добавить фильм")
    print("2. Показать фильмы")
    print("3. Найти фильмы по жанру")
    print("4. Фильтрация по рейтингу")
    print("5. Сортировка по рейтингу")
    print("6. Статистика")
    print("7. Уникальные жанры")
    print("8. Загрузить демонстрационные данные")
    print("0. Выход")


def main():
    movies = []
    while True:
        print_menu()
        choice = input("Выберите действие: ").strip()

        if choice == "0":
            print("Работа программы завершена")
            break
        if choice == "1":
            count = read_int("Сколько фильмов добавить: ", 1, 100)
            for number in range(1, count + 1):
                print(f"--- Фильм {number} ---")
                movies.append(input_movie())
            continue
        if choice == "8":
            movies.extend(demo_movies())
            print("Демонстрационные данные добавлены")
            continue
        if choice not in ("2", "3", "4", "5", "6", "7"):
            print("Ошибка: неизвестный пункт меню")
            continue
        if not movies:
            print("Список фильмов пуст. Сначала добавьте данные")
            continue

        if choice == "2":
            print_movies(movies)
        elif choice == "3":
            genre = read_text("Введите жанр: ")
            print_movies(find_by_genre(movies, genre))
        elif choice == "4":
            min_rating = read_float("Минимальный рейтинг: ", MIN_RATING, MAX_RATING)
            print_movies(filter_by_rating(movies, min_rating))
        elif choice == "5":
            order = input("По убыванию (1) или по возрастанию (2)? ").strip()
            print_movies(sort_movies(movies, "rating", order != "2"))
        elif choice == "6":
            show_statistics(movies)
        elif choice == "7":
            print("Уникальные жанры:", ", ".join(sorted(get_unique_genres(movies))))


if __name__ == "__main__":
    main()
