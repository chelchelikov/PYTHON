from datetime import date

import pytest

from src.models import DateRange


def period(start_day: int, end_day: int) -> DateRange:
    return DateRange(date(2026, 12, start_day), date(2026, 12, end_day))


@pytest.mark.parametrize("first, second, expected", [
    (period(1, 5), period(3, 7), True),    # частичное пересечение справа
    (period(3, 7), period(1, 5), True),    # частичное пересечение слева
    (period(1, 10), period(3, 5), True),   # один период внутри другого
    (period(1, 5), period(1, 5), True),    # совпадают
    (period(1, 5), period(5, 8), False),   # выезд в день заезда следующего гостя
    (period(5, 8), period(1, 5), False),
    (period(1, 3), period(6, 9), False),   # не пересекаются
])
def test_date_range_overlaps(first, second, expected):
    assert first.overlaps(second) is expected
    assert second.overlaps(first) is expected  # отношение симметрично


@pytest.mark.parametrize("start, end, nights", [(1, 2, 1), (1, 8, 7), (1, 31, 30), (5, 5, 0)])
def test_date_range_nights(start, end, nights):
    assert period(start, end).nights == nights
