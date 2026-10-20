"""Лабораторная работа №1. Вариант 5. Температура воздуха."""

import random

MIN_TEMPERATURE = -90.0
MAX_TEMPERATURE = 60.0
HOT_DAY_THRESHOLD = 25.0


def read_int(prompt, min_value):
    while True:
        text = input(prompt)
        if not text.strip().lstrip("-").isdigit():
            print("Ошибка: необходимо ввести целое число")
            continue
        value = int(text)
        if value < min_value:
            print(f"Ошибка: значение должно быть не меньше {min_value}")
            continue
        return value


def read_temperature(prompt):
    while True:
        text = input(prompt).replace(",", ".")
        try:
            value = float(text)
        except ValueError:
            print("Ошибка: необходимо ввести число")
            continue
        if value < MIN_TEMPERATURE or value > MAX_TEMPERATURE:
            print(f"Ошибка: температура должна быть в диапазоне "
                  f"от {MIN_TEMPERATURE} до {MAX_TEMPERATURE}")
            continue
        return value


def input_temperatures(days):
    temperatures = []
    for day in range(1, days + 1):
        temperatures.append(read_temperature(f"Температура за день {day}: "))
    return temperatures


def generate_temperatures(days):
    return [round(random.uniform(-15, 35), 1) for _ in range(days)]


def calculate_average(values):
    total = 0
    for value in values:
        total += value
    return total / len(values)


def find_min_max(values):
    minimum = values[0]
    maximum = values[0]
    for value in values:
        if value < minimum:
            minimum = value
        if value > maximum:
            maximum = value
    return minimum, maximum


def count_above(values, threshold):
    count = 0
    for value in values:
        if value > threshold:
            count += 1
    return count


def longest_positive_period(values):
    """Возвращает длину самого длинного периода и номера его первого и последнего дня."""
    best_length = 0
    best_start = 0
    current_length = 0
    for index, value in enumerate(values):
        if value > 0:
            current_length += 1
            if current_length > best_length:
                best_length = current_length
                best_start = index - current_length + 1
        else:
            current_length = 0
    return best_length, best_start + 1, best_start + best_length


def print_report(temperatures):
    minimum, maximum = find_min_max(temperatures)
    period, start, end = longest_positive_period(temperatures)

    print("\n===== Результаты анализа =====")
    print("Температуры по дням:", ", ".join(f"{t:.1f}" for t in temperatures))
    print(f"Средняя температура: {calculate_average(temperatures):.2f} °C")
    print(f"Минимальная температура: {minimum:.1f} °C")
    print(f"Максимальная температура: {maximum:.1f} °C")
    print(f"Дней с температурой выше нуля: {count_above(temperatures, 0)}")
    print(f"Жарких дней (выше {HOT_DAY_THRESHOLD:.0f} °C): "
          f"{count_above(temperatures, HOT_DAY_THRESHOLD)}")
    if period == 0:
        print("Дней с положительной температурой не было")
    else:
        print(f"Самый длинный период положительной температуры: {period} дн. "
              f"(с {start} по {end} день)")


def main():
    print("===== Анализ температуры воздуха =====")
    days = read_int("Введите количество дней наблюдения: ", 1)
    mode = input("Ввести температуры вручную (1) или сгенерировать случайно (2)? ")
    if mode.strip() == "2":
        temperatures = generate_temperatures(days)
    else:
        temperatures = input_temperatures(days)
    print_report(temperatures)


if __name__ == "__main__":
    main()
