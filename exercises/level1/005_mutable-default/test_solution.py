"""デフォルト引数のバグ修正 のテスト。学習者のコードは solution.py として配置される。"""

import inspect

from solution import add_tag


def test_example_from_description() -> None:
    assert add_tag("a") == ["a"]
    assert add_tag("b") == ["b"]
    assert add_tag("c", ["x"]) == ["x", "c"]


def test_default_is_not_shared_between_calls() -> None:
    first = add_tag("a")
    second = add_tag("b")
    assert first == ["a"]
    assert second == ["b"]
    assert first is not second


def test_does_not_modify_argument() -> None:
    tags = ["x", "y"]
    result = add_tag("z", tags)
    assert result == ["x", "y", "z"]
    assert tags == ["x", "y"]
    assert result is not tags


def test_empty_list_argument() -> None:
    empty: list[str] = []
    assert add_tag("a", empty) == ["a"]
    assert empty == []


def test_default_is_none() -> None:
    """変更可能なリストをデフォルト値にしない(Python の定番は None)。"""
    assert inspect.signature(add_tag).parameters["tags"].default is None
