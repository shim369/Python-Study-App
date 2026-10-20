"""テストしやすい設計に直す のテスト。学習者のコードは solution.py として配置される。"""

import inspect
from datetime import datetime

import pytest

from solution import greeting

MORNING = "おはようございます、太郎さん"
AFTERNOON = "こんにちは、太郎さん"
EVENING = "こんばんは、太郎さん"


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 20, hour, minute)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (at(4, 59), EVENING),
        (at(5, 0), MORNING),  # 境界: 5時ちょうどから朝
        (at(7, 30), MORNING),
        (at(10, 59), MORNING),
        (at(11, 0), AFTERNOON),  # 報告のあったバグ: 11時ちょうどは昼
        (at(17, 59), AFTERNOON),
        (at(18, 0), EVENING),  # 境界: 18時ちょうどから夜
        (at(23, 59), EVENING),
        (at(0, 0), EVENING),
    ],
)
def test_greeting_by_time(now: datetime, expected: str) -> None:
    assert greeting("太郎", now=now) == expected


def test_name_is_used() -> None:
    assert greeting("Hanako", now=at(12)) == "こんにちは、Hanakoさん"


def test_now_can_be_passed_positionally() -> None:
    assert greeting("太郎", at(8)) == MORNING


def test_without_now_uses_current_time() -> None:
    assert greeting("太郎") in {MORNING, AFTERNOON, EVENING}


def test_default_is_none() -> None:
    """デフォルト値に datetime.now() を書くと、関数を定義した時刻で固定されてしまう。"""
    assert inspect.signature(greeting).parameters["now"].default is None
