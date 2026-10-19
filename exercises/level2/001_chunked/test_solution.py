"""チャンク分割ジェネレータ のテスト。学習者のコードは solution.py として配置される。"""

from collections.abc import Iterator
from itertools import islice

import pytest

from solution import chunked


def test_example_from_description() -> None:
    assert list(chunked([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


@pytest.mark.parametrize(
    ("data", "size", "expected"),
    [
        ([1, 2, 3, 4], 2, [[1, 2], [3, 4]]),  # 割り切れる
        ([1, 2, 3], 5, [[1, 2, 3]]),  # size が要素数より大きい
        ([1, 2, 3], 1, [[1], [2], [3]]),  # size=1
        ([], 3, []),  # 空
        ("abcdefg", 3, [["a", "b", "c"], ["d", "e", "f"], ["g"]]),  # 文字列もイテラブル
    ],
)
def test_chunks(data: list[object], size: int, expected: list[list[object]]) -> None:
    assert list(chunked(data, size)) == expected


def test_returns_lazy_iterator() -> None:
    result = chunked([1, 2, 3], 2)
    assert isinstance(result, Iterator)
    assert next(result) == [1, 2]


def test_works_with_generator_input() -> None:
    squares = (n * n for n in range(5))
    assert list(chunked(squares, 2)) == [[0, 1], [4, 9], [16]]


def endless_numbers(limit: int = 1000) -> Iterator[int]:
    """無限イテレータの代わり。取り出しすぎたら失敗させてハングを防ぐ。"""
    n = 0
    while True:
        if n >= limit:
            raise RuntimeError("入力を全部読もうとしています(一度にリスト化していませんか?)")
        yield n
        n += 1


def test_infinite_iterator() -> None:
    first_three = list(islice(chunked(endless_numbers(), 3), 3))
    assert first_three == [[0, 1, 2], [3, 4, 5], [6, 7, 8]]


@pytest.mark.parametrize("size", [0, -1])
def test_invalid_size_raises(size: int) -> None:
    with pytest.raises(ValueError):
        list(chunked([1, 2], size))
