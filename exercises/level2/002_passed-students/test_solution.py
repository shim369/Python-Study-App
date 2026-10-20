"""合格者の一覧 のテスト。学習者のコードは solution.py として配置される。"""

import pytest

from solution import passed_students


def test_example_from_description() -> None:
    scores = {"sato": [80, 90], "suzuki": [60, 70], "tanaka": [100]}
    assert passed_students(scores, 70) == ["tanaka", "sato"]


@pytest.mark.parametrize(
    ("scores", "threshold", "expected"),
    [
        ({}, 50, []),  # 空
        ({"a": []}, 0, []),  # 点数なしは対象外
        ({"a": [70]}, 70, ["a"]),  # ちょうど threshold は合格
        ({"a": [69, 70]}, 69.6, []),  # 平均 69.5 は丸めない
        ({"b": [80], "a": [80], "c": [90]}, 0, ["c", "a", "b"]),  # 同点は名前順
        ({"x": [10, 20, 30], "y": [25]}, 20, ["y", "x"]),
    ],
)
def test_rules(scores: dict[str, list[int]], threshold: float, expected: list[str]) -> None:
    assert passed_students(scores, threshold) == expected


def test_does_not_modify_argument() -> None:
    scores = {"a": [50], "b": []}
    passed_students(scores, 0)
    assert scores == {"a": [50], "b": []}


def test_many_students() -> None:
    scores = {f"s{n:03}": [n] for n in range(100)}
    assert passed_students(scores, 97) == ["s099", "s098", "s097"]
