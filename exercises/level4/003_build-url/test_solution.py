"""クエリ付きURLの組み立て のテスト。学習者のコードは solution.py として配置される。"""

import pytest

from solution import build_url

BASE = "https://api.example.com"


def test_example_from_description() -> None:
    params: dict[str, str | int | list[str] | None] = {
        "q": "python 3",
        "page": 2,
        "tag": ["web", "api"],
    }
    assert (
        build_url("https://api.example.com/", "/v1/search", params)
        == "https://api.example.com/v1/search?q=python%203&page=2&tag=web&tag=api"
    )


@pytest.mark.parametrize(
    ("base", "path"),
    [(BASE, "v1/users"), (BASE + "/", "v1/users"), (BASE, "/v1/users"), (BASE + "/", "/v1/users")],
)
def test_single_slash_between_base_and_path(base: str, path: str) -> None:
    assert build_url(base, path) == "https://api.example.com/v1/users"


@pytest.mark.parametrize(
    ("params", "query"),
    [
        (None, ""),
        ({}, ""),
        ({"a": None, "b": None}, ""),  # 全部 None なら ? を付けない
        ({"a": "1", "b": None, "c": 3}, "?a=1&c=3"),  # None は除く・順番を保つ
        ({"path": "a/b c"}, "?path=a%2Fb%20c"),  # / と空白のエンコード
        ({"q": "日本"}, "?q=%E6%97%A5%E6%9C%AC"),  # UTF-8
        ({"q": "a&b=c"}, "?q=a%26b%3Dc"),  # & と = もエンコード
        ({"id": ["1", "2"]}, "?id=1&id=2"),  # リストは同じキーを繰り返す
        ({"empty": ""}, "?empty="),  # 空文字列は残す
    ],
)
def test_query(params: dict[str, str | int | list[str] | None] | None, query: str) -> None:
    assert build_url(BASE, "items", params) == f"{BASE}/items{query}"
