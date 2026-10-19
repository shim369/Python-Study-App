"""<演習タイトル> のテスト。学習者のコードは solution.py として配置される。"""

import pytest

from solution import function_name


def test_basic() -> None:
    assert function_name("...") == ...


@pytest.mark.parametrize(
    ("arg", "expected"),
    [
        ("...", ...),  # 典型ケース
        ("", ...),  # 空・境界値
    ],
)
def test_cases(arg: str, expected: int) -> None:
    assert function_name(arg) == expected
