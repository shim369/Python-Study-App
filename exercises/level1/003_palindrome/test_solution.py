"""回文の判定 のテスト。学習者のコードは solution.py として配置される。"""

import pytest

from solution import is_palindrome


def test_examples_from_description() -> None:
    assert is_palindrome("A man, a plan, a canal: Panama") is True
    assert is_palindrome("race a car") is False


@pytest.mark.parametrize(
    "text",
    [
        "",  # 空文字列
        "!!! ...",  # 判定に使う文字がない
        "a",  # 1文字
        "Aa",  # 大文字小文字を区別しない
        "No 'x' in Nixon",
        "12321",
        "1 2-3 2 1",  # 記号と空白は無視
        "abba",  # 偶数長
    ],
)
def test_palindromes(text: str) -> None:
    assert is_palindrome(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "ab",
        "abca",
        "Abc cbA d",
        "0P",  # 数字と英字は別の文字
        "palindrome",
    ],
)
def test_not_palindromes(text: str) -> None:
    assert is_palindrome(text) is False
