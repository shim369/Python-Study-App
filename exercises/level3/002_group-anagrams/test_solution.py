"""アナグラムのグループ分け のテスト。学習者のコードは solution.py として配置される。"""

import pytest

from solution import group_anagrams


def test_example_from_description() -> None:
    words = ["eat", "tea", "tan", "ate", "nat", "bat"]
    assert group_anagrams(words) == [["eat", "tea", "ate"], ["tan", "nat"], ["bat"]]


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ([], []),  # 空
        (["a"], [["a"]]),  # 1単語
        (["abc", "def", "ghi"], [["abc"], ["def"], ["ghi"]]),  # アナグラムなし
        (["ab", "ba", "ab"], [["ab", "ba", "ab"]]),  # 重複もそのまま
        (["aab", "abb", "bab", "baa"], [["aab", "baa"], ["abb", "bab"]]),  # 文字の個数も区別
        (["", "", "x"], [["", ""], ["x"]]),  # 空文字列もアナグラム同士
        (["listen", "google", "silent", "enlist"], [["listen", "silent", "enlist"], ["google"]]),
    ],
)
def test_groups(words: list[str], expected: list[list[str]]) -> None:
    assert group_anagrams(words) == expected


def test_does_not_modify_argument() -> None:
    words = ["b", "a"]
    group_anagrams(words)
    assert words == ["b", "a"]
