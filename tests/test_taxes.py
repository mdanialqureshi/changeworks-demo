from decimal import Decimal

import pytest

from quillstack_billing.errors import CurrencyMismatchError
from quillstack_billing.money import Money
from quillstack_billing.regions import TaxCategory, region
from quillstack_billing.taxes import TaxableLine, compute_taxes, exact_tax


def lines(code: str, *items: tuple[str, TaxCategory]) -> list[TaxableLine]:
    return [TaxableLine(Money.of(a, code), c) for a, c in items]


STD, RED = TaxCategory.STANDARD, TaxCategory.REDUCED


def test_exact_tax() -> None:
    assert exact_tax(Decimal("50"), Decimal("8.25"), inclusive=False) == (
        Decimal("4.125")
    )
    assert exact_tax(Decimal("108"), Decimal("8"), inclusive=True) == 8


def test_exclusive_line_level_half_up() -> None:
    summary = compute_taxes(
        region("ALD"),
        lines("GBP", ("30.00", STD), ("9.98", RED)),
        code="GBP",
    )
    assert summary.tax == Money.of("6.50", "GBP")  # 6.00 + 0.499 -> 0.50
    assert summary.net == Money.of("39.98", "GBP")
    assert summary.gross == Money.of("46.48", "GBP")
    assert [r.rate for r in summary.by_rate] == [Decimal(20), Decimal(5)]


def test_line_level_rounds_each_line() -> None:
    # Two lines of 0.03 at 20%: 0.006 each, rounded to 0.01 each.
    summary = compute_taxes(
        region("ALD"), lines("GBP", ("0.03", STD), ("0.03", STD)), code="GBP"
    )
    assert summary.tax == Money.of("0.02", "GBP")


def test_brightwater_fractional_rate() -> None:
    summary = compute_taxes(
        region("BRW"), lines("USD", ("99.99", STD)), code="USD"
    )
    assert summary.tax == Money.of("8.25", "USD")


def test_emberlyn_rounds_half_even_to_the_fils() -> None:
    summary = compute_taxes(
        region("EMB"),
        lines("KWD", ("0.090", STD), ("0.110", STD)),
        code="KWD",
    )
    # 0.0045 -> 0.004 (even) and 0.0055 -> 0.006 (even)
    assert summary.tax == Money.of("0.010", "KWD")


def test_duskfell_extracts_tax_and_drops_fractions() -> None:
    summary = compute_taxes(
        region("DSF"),
        lines("JPY", ("3300", STD), ("1080", RED), ("150", STD)),
        code="JPY",
    )
    # 300 + 80 + 13.63 -> 13
    assert summary.tax == Money.of("393", "JPY")
    assert summary.gross == Money.of("4530", "JPY")
    assert summary.net == Money.of("4137", "JPY")


def test_corvane_rounds_once_per_rate() -> None:
    summary = compute_taxes(
        region("CRV"),
        lines("EUR", ("0.03", STD), ("0.03", STD), ("12.34", RED)),
        code="EUR",
    )
    by_rate = {r.rate: r.tax for r in summary.by_rate}
    # line level would give 0.01 + 0.01; once per rate 0.0114 -> 0.01
    assert by_rate[Decimal(19)] == Money.of("0.01", "EUR")
    assert by_rate[Decimal(7)] == Money.of("0.86", "EUR")


def test_exempt_customer_pays_no_tax() -> None:
    summary = compute_taxes(
        region("ALD"), lines("GBP", ("100", STD)), code="GBP", exempt=True
    )
    assert summary.tax.is_zero
    assert summary.gross == Money.of("100", "GBP")


def test_zero_and_exempt_categories() -> None:
    summary = compute_taxes(
        region("ALD"),
        lines("GBP", ("10", TaxCategory.ZERO), ("5", TaxCategory.EXEMPT)),
        code="GBP",
    )
    assert summary.tax.is_zero
    assert summary.net == Money.of("15", "GBP")


def test_lines_must_match_invoice_currency() -> None:
    with pytest.raises(CurrencyMismatchError):
        compute_taxes(region("ALD"), lines("EUR", ("1", STD)), code="GBP")


def test_no_lines_no_tax() -> None:
    summary = compute_taxes(region("ALD"), [], code="GBP")
    assert summary.by_rate == ()
    assert summary.tax == Money.zero("GBP")
