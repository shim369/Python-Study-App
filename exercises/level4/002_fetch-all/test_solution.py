"""同時実行数を制限した並行取得 のテスト。学習者のコードは solution.py として配置される。"""

import asyncio

import pytest

from solution import fetch_all


class FakeFetcher:
    """通信の代わりに sleep し、同時に実行されている数の最大値を記録する。"""

    def __init__(self, delays: dict[str, float] | None = None) -> None:
        self.delays = delays or {}
        self.running = 0
        self.max_running = 0
        self.calls: list[str] = []

    async def __call__(self, url: str) -> str:
        self.calls.append(url)
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        try:
            await asyncio.sleep(self.delays.get(url, 0.02))
            if url.endswith("/error"):
                raise ConnectionError(url)
            return f"body of {url}"
        finally:
            self.running -= 1


def urls(count: int) -> list[str]:
    return [f"https://example.com/{n}" for n in range(count)]


def test_results_keep_input_order() -> None:
    # 先のURLほど遅く終わるようにして、終わった順ではなく入力順で返すことを確かめる
    targets = urls(4)
    fetcher = FakeFetcher({url: 0.05 - i * 0.01 for i, url in enumerate(targets)})
    result = asyncio.run(fetch_all(targets, fetcher, limit=4))
    assert result == [f"body of {url}" for url in targets]


@pytest.mark.parametrize(("count", "limit", "expected_max"), [(10, 3, 3), (10, 1, 1), (2, 5, 2)])
def test_concurrency_is_limited_but_used(count: int, limit: int, expected_max: int) -> None:
    fetcher = FakeFetcher()
    asyncio.run(fetch_all(urls(count), fetcher, limit=limit))
    assert fetcher.max_running == expected_max  # limit を超えず、limit まではちゃんと並行
    assert sorted(fetcher.calls) == sorted(urls(count))  # 全部1回ずつ取得


def test_empty_urls() -> None:
    assert asyncio.run(fetch_all([], FakeFetcher(), limit=3)) == []


def test_error_is_propagated() -> None:
    with pytest.raises(ConnectionError):
        asyncio.run(fetch_all(["https://example.com/error"], FakeFetcher(), limit=2))


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_limit(limit: int) -> None:
    with pytest.raises(ValueError):
        asyncio.run(fetch_all(urls(1), FakeFetcher(), limit=limit))
