"""ランレングス圧縮 のテスト。学習者のコードは solution.py として配置される。"""

import pytest

from solution import decode, encode


def test_examples_from_description() -> None:
    assert encode("aaabccdddd") == [("a", 3), ("b", 1), ("c", 2), ("d", 4)]
    assert decode([("x", 2), ("y", 1)]) == "xxy"


@pytest.mark.parametrize(
    ("text", "pairs"),
    [
        ("", []),  # 空
        ("a", [("a", 1)]),  # 1文字
        ("aba", [("a", 1), ("b", 1), ("a", 1)]),  # 連続していない同じ文字
        ("aAA", [("a", 1), ("A", 2)]),  # 大文字小文字は別
        ("  !!", [(" ", 2), ("!", 2)]),  # 空白・記号
        ("zzzzzzzzzzzz", [("z", 12)]),  # 2桁の回数
        ("ああいい", [("あ", 2), ("い", 2)]),
    ],
)
def test_encode_and_decode(text: str, pairs: list[tuple[str, int]]) -> None:
    assert encode(text) == pairs
    assert decode(pairs) == text


@pytest.mark.parametrize("text", ["mississippi", "aaaaabbbbbaaaaa", "x" * 1000 + "y"])
def test_round_trip(text: str) -> None:
    assert decode(encode(text)) == text
