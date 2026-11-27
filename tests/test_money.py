from decimal import Decimal

import pytest

from quillstack_billing.errors import (
    CurrencyMismatchError,
    UnknownCurrencyError,
)
from quillstack_billing.money import Money, currency, sum_money, to_decimal
from quillstack_billing.rounding import RoundingMode


def gbp(text: str) -> Money:
    return Money.of(text, "GBP")


def test_of_accepts_strings_ints_and_decimals() -> None:
    assert gbp("12.50").amount == Decimal("12.50")
    assert Money.of(3, "usd").currency.code == "USD"
    assert Money.of(Decimal("1.1"), "EUR").amount == Decimal("1.1")


def test_floats_are_refused() -> None:
    with pytest.raises(TypeError):
        Money.of(0.1, "GBP")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        to_decimal(True)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["abc", "NaN", "Infinity", ""])
def test_non_numbers_are_refused(bad: str) -> None:
    with pytest.raises(ValueError):
        to_decimal(bad)


def test_thousands_separators_are_allowed() -> None:
    assert to_decimal("1,234.50") == Decimal("1234.50")


def test_unknown_currency() -> None:
    with pytest.raises(UnknownCurrencyError):
        currency("XXX")


def test_addition_and_subtraction() -> None:
    assert gbp("1.10") + gbp("2.25") == gbp("3.35")
    assert gbp("5") - gbp("7.5") == gbp("-2.5")
    assert -gbp("3") == gbp("-3")
    assert abs(gbp("-3")) == gbp("3")


def test_sum_starts_from_zero() -> None:
    assert sum([gbp("1"), gbp("2")]) == gbp("3")
    assert sum_money([], "GBP") == Money.zero("GBP")


@pytest.mark.parametrize("op", ["add", "sub"])
def test_mixing_currencies_raises(op: str) -> None:
    a, b = gbp("1"), Money.of("1", "EUR")
    with pytest.raises(CurrencyMismatchError):
        if op == "add":
            a + b
        else:
            a - b


def test_sum_money_refuses_other_currencies() -> None:
    with pytest.raises(CurrencyMismatchError):
        sum_money([gbp("1"), Money.of("1", "USD")], "GBP")


def test_multiplication_keeps_precision() -> None:
    assert (gbp("0.333") * 3).amount == Decimal("0.999")
    assert (Decimal("2") * gbp("1.5")) == gbp("3.0")
    with pytest.raises(TypeError):
        gbp("1") * 1.5  # type: ignore[operator]
    with pytest.raises(TypeError):
        gbp("1") * gbp("2")  # type: ignore[operator]


def test_ordering_within_one_currency() -> None:
    assert gbp("1") < gbp("2")
    assert gbp("2") >= gbp("2.00")
    assert max(gbp("3"), gbp("1"), gbp("2")) == gbp("3")


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (RoundingMode.HALF_UP, "2.35"),
        (RoundingMode.HALF_EVEN, "2.34"),
        (RoundingMode.DOWN, "2.34"),
        (RoundingMode.UP, "2.35"),
    ],
)
def test_rounded(mode: RoundingMode, expected: str) -> None:
    assert gbp("2.345").rounded(mode).amount == Decimal(expected)


def test_rounding_respects_minor_units() -> None:
    assert Money.of("1234.5", "JPY").rounded().amount == Decimal("1235")
    assert Money.of("1.2345", "KWD").rounded().amount == Decimal("1.235")


def test_str_and_format() -> None:
    assert str(gbp("1234.5")) == "GBP 1,234.50"
    assert gbp("1234.5").format() == "£1,234.50"
    assert gbp("-3").format() == "-£3.00"
    assert str(Money.of("1200", "JPY")) == "JPY 1,200"
    assert Money.of("2.5", "KWD").plain() == "2.500"


def test_allocate_even_split() -> None:
    shares = gbp("100.00").allocate([1, 1, 1, 1])
    assert shares == [gbp("25.00")] * 4


def test_allocate_by_weight() -> None:
    shares = gbp("90.00").allocate([1, 2])
    assert shares == [gbp("30.00"), gbp("60.00")]


@pytest.mark.parametrize("ratios", [[], [0, 0], [1, -1]])
def test_allocate_rejects_bad_ratios(ratios: list[int]) -> None:
    with pytest.raises(ValueError):
        gbp("10").allocate(ratios)


def test_money_is_hashable_and_immutable() -> None:
    assert len({gbp("1.0"), gbp("1.00")}) == 1
    with pytest.raises(AttributeError):
        gbp("1").amount = Decimal(2)  # type: ignore[misc]
