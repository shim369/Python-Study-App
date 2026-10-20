"""アクセスログの解析 のテスト。学習者のコードは solution.py として配置される。"""

import pytest

from solution import LogEntry, parse_access_log

SAMPLE = '127.0.0.1 - - [20/Oct/2026:10:15:32 +0900] "GET /index.html HTTP/1.1" 200 1534'


def test_example_from_description() -> None:
    assert parse_access_log(SAMPLE) == LogEntry("127.0.0.1", "GET", "/index.html", 200, 1534)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            "10.0.0.5 - alice [01/Jan/2027:00:00:00 +0000] "
            '"POST /api/items?id=3&x=y HTTP/2.0" 201 -',
            LogEntry("10.0.0.5", "POST", "/api/items?id=3&x=y", 201, 0),  # サイズ "-" は 0
        ),
        (
            '::1 - - [20/Oct/2026:23:59:59 +0900] "DELETE /users/42 HTTP/1.1" 404 0',
            LogEntry("::1", "DELETE", "/users/42", 404, 0),
        ),
        (SAMPLE + "\n", LogEntry("127.0.0.1", "GET", "/index.html", 200, 1534)),  # 末尾の改行
        (f"  {SAMPLE}  ", LogEntry("127.0.0.1", "GET", "/index.html", 200, 1534)),  # 前後の空白
    ],
)
def test_valid_lines(line: str, expected: LogEntry) -> None:
    assert parse_access_log(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "",
        "hello world",
        '127.0.0.1 - - [20/Oct/2026:10:15:32 +0900] "GET /index.html HTTP/1.1" 200',  # サイズ無し
        '127.0.0.1 - - [20/Oct/2026:10:15:32 +0900] "GET /index.html HTTP/1.1" OK 1534',
        '127.0.0.1 - - [20/Oct/2026:10:15:32 +0900] "GET /index.html HTTP/1.1" 2000 1534',
        '127.0.0.1 - - [20/Oct/2026:10:15:32 +0900] "get /index.html HTTP/1.1" 200 1534',
        '127.0.0.1 - - 20/Oct/2026:10:15:32 "GET /index.html HTTP/1.1" 200 1534',  # [] なし
        SAMPLE + " extra",  # 余計な文字
    ],
)
def test_invalid_lines(line: str) -> None:
    assert parse_access_log(line) is None
