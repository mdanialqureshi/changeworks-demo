"""Tax calculation for a set of invoice lines.

Each line arrives as its amount after discounts and its tax category.
For regions whose prices exclude tax, tax is added on top; for regions
whose prices include it, tax is extracted from the amount.

Rounding follows the region: at ``line`` level each line's tax is
rounded and the results are added up; at ``invoice`` level the exact
tax for each rate is added up first and rounded once. Both use the
region's :class:`~quillstack_billing.rounding.RoundingMode`.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from .errors import CurrencyMismatchError
from .money import Currency, Money, currency, sum_money
from .regions import TaxCategory, TaxRegion
from .rounding import RoundingLevel, round_amount

HUNDRED = Decimal(100)


@dataclass(frozen=True)
class TaxableLine:
    """A line's amount after discounts, and its category."""

    amount: Money
    category: TaxCategory = TaxCategory.STANDARD


@dataclass(frozen=True)
class RateTotal:
    """Net and tax for every line taxed at one rate."""

    rate: Decimal
    net: Money
    tax: Money


@dataclass(frozen=True)
class TaxSummary:
    """The tax on an invoice, by rate and in total."""

    currency: Currency
    by_rate: tuple[RateTotal, ...]

    @property
    def net(self) -> Money:
        return sum_money((r.net for r in self.by_rate), self.currency)

    @property
    def tax(self) -> Money:
        return sum_money((r.tax for r in self.by_rate), self.currency)

    @property
    def gross(self) -> Money:
        return self.net + self.tax


def exact_tax(amount: Decimal, rate: Decimal, *, inclusive: bool) -> Decimal:
    """The unrounded tax on ``amount`` at ``rate`` percent.

    >>> exact_tax(Decimal("100"), Decimal("20"), inclusive=False)
    Decimal('20')
    >>> exact_tax(Decimal("120"), Decimal("20"), inclusive=True)
    Decimal('20')
    """
    if inclusive:
        return amount * rate / (HUNDRED + rate)
    return amount * rate / HUNDRED


def split_inclusive(
    gross: Money, rate: Decimal, tax_region: TaxRegion
) -> tuple[Money, Money]:
    """Split a tax-inclusive amount into (net, tax), rounding the tax.

    The net is whatever is left, so net + tax is always exactly
    ``gross``.
    """
    raw = exact_tax(gross.amount, rate, inclusive=True)
    tax = Money(
        round_amount(raw, gross.currency.minor_units, tax_region.rounding),
        gross.currency,
    )
    return gross - tax, tax


def compute_taxes(
    tax_region: TaxRegion,
    lines: Iterable[TaxableLine],
    *,
    code: str | Currency,
    exempt: bool = False,
) -> TaxSummary:
    """Tax for ``lines`` under ``tax_region``, in currency ``code``.

    ``exempt`` (a tax-exempt customer) taxes every line at 0%.
    """
    cur = currency(code)
    inclusive = tax_region.prices_include_tax
    # rate -> [sum of amounts, sum of exact tax, sum of rounded tax]
    buckets: dict[Decimal, list[Decimal]] = {}
    for line in lines:
        if line.amount.currency != cur:
            raise CurrencyMismatchError(
                f"line in {line.amount.currency}, invoice in {cur}"
            )
        rate = Decimal(0) if exempt else tax_region.rate(line.category)
        raw = exact_tax(line.amount.amount, rate, inclusive=inclusive)
        rounded = round_amount(raw, cur.minor_units, tax_region.rounding)
        bucket = buckets.setdefault(rate, [Decimal(0)] * 3)
        bucket[0] += line.amount.amount
        bucket[1] += raw
        bucket[2] += rounded

    totals = []
    for rate in sorted(buckets, reverse=True):
        amount, raw_tax, line_tax = buckets[rate]
        if tax_region.rounding_level is RoundingLevel.INVOICE:
            tax = raw_tax.quantize(cur.exponent)
        else:
            tax = line_tax
        net = amount - tax if inclusive else amount
        totals.append(RateTotal(rate, Money(net, cur), Money(tax, cur)))
    return TaxSummary(cur, tuple(totals))
