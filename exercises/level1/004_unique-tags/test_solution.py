"""タグの重複除去 のテスト。学習者のコードは solution.py として配置される。"""

import pytest

from solution import unique_tags


def test_example_from_description() -> None:
    assert unique_tags(["Python", " php ", "python", "PHP", "", "Go"]) == ["Python", "php", "Go"]


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ([], []),  # 空
        (["a"], ["a"]),  # 1要素
        (["b", "a", "b", "c", "a"], ["b", "a", "c"]),  # 最初に出てきた順
        (["RUST", "rust", "Rust"], ["RUST"]),  # 最初の表記を残す
        (["  ", "\t", ""], []),  # 空白だけのタグは捨てる
        (["web api", "Web API "], ["web api"]),  # 途中の空白はそのまま
    ],
)
def test_rules(tags: list[str], expected: list[str]) -> None:
    assert unique_tags(tags) == expected


def test_does_not_modify_argument() -> None:
    tags = [" x ", "X", "y"]
    unique_tags(tags)
    assert tags == [" x ", "X", "y"]


def test_many_tags() -> None:
    tags = [f"tag{n % 100}" for n in range(10_000)]
    assert unique_tags(tags) == [f"tag{n}" for n in range(100)]
