"""営業日を数える のテスト。学習者のコードは solution.py として配置される。"""

from datetime import date

import pytest

from solution import count_business_days

MON = date(2026, 10, 19)
FRI = date(2026, 10, 23)
SAT = date(2026, 10, 24)
SUN = date(2026, 10, 25)
NEXT_MON = date(2026, 10, 26)


def test_examples_from_description() -> None:
    assert count_business_days(MON, SUN) == 5
    assert count_business_days(MON, FRI, [date(2026, 10, 21)]) == 4


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (MON, MON, 1),  # 同じ日(平日)
        (SAT, SAT, 0),  # 同じ日(土曜)
        (SAT, SUN, 0),  # 週末だけ
        (FRI, NEXT_MON, 2),  # 週末をまたぐ
        (MON, NEXT_MON, 6),
        (date(2026, 10, 1), date(2026, 10, 31), 22),  # 1か月
        (date(2026, 12, 28), date(2027, 1, 8), 10),  # 年をまたぐ
        (NEXT_MON, MON, 0),  # start が end より後
    ],
)
def test_counts(start: date, end: date, expected: int) -> None:
    assert count_business_days(start, end) == expected


def test_holidays_on_weekend_are_ignored() -> None:
    assert count_business_days(MON, SUN, {SAT, SUN}) == 5


def test_holidays_outside_range_are_ignored() -> None:
    assert count_business_days(MON, FRI, [date(2025, 1, 1), NEXT_MON]) == 5


def test_holidays_can_be_any_iterable() -> None:
    holidays = (d for d in [date(2026, 10, 20), date(2026, 10, 22)])
    assert count_business_days(MON, FRI, holidays) == 3
