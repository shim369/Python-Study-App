"""単語の出現回数 のテスト。学習者のコードは solution.py として配置される。"""

import pytest

from solution import word_frequency


def test_example_from_description() -> None:
    assert word_frequency("The cat and the hat.") == {"the": 2, "cat": 1, "and": 1, "hat": 1}


def test_empty_string_returns_empty_dict() -> None:
    assert word_frequency("") == {}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hello hello HELLO", {"hello": 3}),  # 大文字小文字を区別しない
        ("a  b\tb\n\nc", {"a": 1, "b": 2, "c": 1}),  # 連続した空白・タブ・改行
        ("Wow! Really? yes, yes.", {"wow": 1, "really": 1, "yes": 2}),  # 前後の記号
        ("... !!! ok", {"ok": 1}),  # 記号だけの語は数えない
        ("don't stop", {"don't": 1, "stop": 1}),  # 単語の途中の記号はそのまま
        ("   ", {}),  # 空白だけ
    ],
)
def test_rules(text: str, expected: dict[str, int]) -> None:
    assert word_frequency(text) == expected


def test_many_words() -> None:
    text = " ".join(["python"] * 50 + ["php"] * 7 + ["Go"])
    assert word_frequency(text) == {"python": 50, "php": 7, "go": 1}
