"""リトライするデコレータ のテスト。学習者のコードは solution.py として配置される。"""

import pytest

from solution import retry


class Flaky:
    """最初の fail_times 回だけ error を送出し、その後は "ok" を返す。呼ばれた回数を数える。"""

    def __init__(self, fail_times: int, error: Exception | None = None) -> None:
        self.fail_times = fail_times
        self.error = error or ConnectionError("一時的な失敗")
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.error
        return "ok"


@pytest.mark.parametrize(
    ("times", "fail_times", "expected_calls"), [(3, 0, 1), (3, 2, 3), (5, 1, 2)]
)
def test_succeeds_after_retries(times: int, fail_times: int, expected_calls: int) -> None:
    flaky = Flaky(fail_times)
    assert retry(times, (ConnectionError,))(flaky)() == "ok"
    assert flaky.calls == expected_calls


def test_raises_last_error_after_all_attempts_fail() -> None:
    flaky = Flaky(fail_times=10)
    with pytest.raises(ConnectionError):
        retry(3, (ConnectionError,))(flaky)()
    assert flaky.calls == 3


def test_other_exceptions_are_not_retried() -> None:
    flaky = Flaky(fail_times=1, error=KeyError("x"))
    with pytest.raises(KeyError):
        retry(3, (ConnectionError,))(flaky)()
    assert flaky.calls == 1


def test_default_retries_any_exception() -> None:
    flaky = Flaky(fail_times=1, error=ValueError("x"))
    assert retry(2)(flaky)() == "ok"


def test_times_one_means_no_retry() -> None:
    flaky = Flaky(fail_times=1)
    with pytest.raises(ConnectionError):
        retry(1, (ConnectionError,))(flaky)()
    assert flaky.calls == 1


def test_arguments_and_metadata_are_kept() -> None:
    @retry(times=2)
    def greet(name: str, *, punctuation: str = "!") -> str:
        """挨拶する"""
        return f"hello {name}{punctuation}"

    assert greet("py", punctuation="?") == "hello py?"
    assert greet.__name__ == "greet"
    assert greet.__doc__ == "挨拶する"


@pytest.mark.parametrize("times", [0, -1])
def test_invalid_times(times: int) -> None:
    with pytest.raises(ValueError):
        retry(times)
