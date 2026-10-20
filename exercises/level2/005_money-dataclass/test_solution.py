"""お金を表す値オブジェクト のテスト。学習者のコードは solution.py として配置される。"""

import dataclasses

import pytest

from solution import CurrencyMismatchError, Money


def test_add_same_currency() -> None:
    total = Money(1000, "JPY") + Money(200, "JPY")
    assert total == Money(1200, "JPY")
    assert str(total) == "1,200 JPY"


@pytest.mark.parametrize(
    ("money", "text"),
    [
        (Money(0, "JPY"), "0 JPY"),
        (Money(999, "USD"), "999 USD"),
        (Money(1234567, "EUR"), "1,234,567 EUR"),
        (Money(-500, "USD"), "-500 USD"),
    ],
)
def test_str(money: Money, text: str) -> None:
    assert str(money) == text


def test_value_equality_and_hash() -> None:
    assert Money(100, "JPY") == Money(100, "JPY")
    assert Money(100, "JPY") != Money(100, "USD")
    assert Money(100, "JPY") != Money(101, "JPY")
    assert len({Money(100, "JPY"), Money(100, "JPY"), Money(1, "JPY")}) == 2


def test_is_immutable() -> None:
    money = Money(100, "JPY")
    with pytest.raises(dataclasses.FrozenInstanceError):
        money.amount = 200  # type: ignore[misc]


def test_add_returns_new_object() -> None:
    a = Money(1, "JPY")
    b = Money(2, "JPY")
    assert (a + b) is not a
    assert a == Money(1, "JPY")


def test_currency_mismatch() -> None:
    with pytest.raises(CurrencyMismatchError) as info:
        Money(1, "JPY") + Money(1, "USD")
    assert "JPY" in str(info.value)
    assert "USD" in str(info.value)
    assert isinstance(info.value, ValueError)


FULLWIDTH_JPY = "\uff2a\uff30\uff39"  # 全角英字の JPY(isupper も isalpha も True になる)


@pytest.mark.parametrize("code", ["jpy", "JP", "JPYY", "", "J1Y", FULLWIDTH_JPY])
def test_invalid_currency(code: str) -> None:
    with pytest.raises(ValueError):
        Money(1, code)
