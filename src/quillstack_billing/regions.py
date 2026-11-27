"""Tax regions Quillstack invoices in.

The regions are fictional, but each behaves like a real VAT or sales
tax regime: a set of rates by category, a default currency, whether
listed prices include tax, how and where tax is rounded, and the time
zone that decides an invoice's tax point date.

``docs/tax-regions.md`` is the human-readable copy of :data:`REGIONS`.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, tzinfo
from decimal import Decimal
from enum import StrEnum
from functools import cache
from types import MappingProxyType

from .errors import UnknownRegionError
from .rounding import RoundingLevel, RoundingMode


class TaxCategory(StrEnum):
    """What kind of supply a line is, for picking its tax rate."""

    STANDARD = "standard"
    REDUCED = "reduced"
    ZERO = "zero"
    EXEMPT = "exempt"


@dataclass(frozen=True)
class TaxRegion:
    """One tax regime.

    ``rates`` holds percentages for the categories that carry tax;
    ``zero`` and ``exempt`` are always 0%.
    """

    code: str
    name: str
    currency: str
    timezone: str
    rates: Mapping[TaxCategory, Decimal]
    prices_include_tax: bool = False
    rounding: RoundingMode = RoundingMode.HALF_UP
    rounding_level: RoundingLevel = RoundingLevel.LINE
    notes: str = field(default="", compare=False)

    def rate(self, category: TaxCategory | str) -> Decimal:
        """The percentage rate for ``category`` in this region."""
        category = TaxCategory(category)
        if category in (TaxCategory.ZERO, TaxCategory.EXEMPT):
            return Decimal(0)
        try:
            return self.rates[category]
        except KeyError:
            raise UnknownRegionError(
                f"{self.code} has no {category} rate"
            ) from None


def _rates(**percent: str) -> Mapping[TaxCategory, Decimal]:
    return MappingProxyType(
        {TaxCategory(k): Decimal(v) for k, v in percent.items()}
    )


REGIONS: dict[str, TaxRegion] = {
    r.code: r
    for r in (
        TaxRegion(
            code="ALD",
            name="Aldermere",
            currency="GBP",
            timezone="Europe/London",
            rates=_rates(standard="20", reduced="5"),
        ),
        TaxRegion(
            code="BRW",
            name="Brightwater",
            currency="USD",
            timezone="America/New_York",
            rates=_rates(standard="8.25", reduced="4.5"),
        ),
        TaxRegion(
            code="CRV",
            name="Corvane",
            currency="EUR",
            timezone="Europe/Berlin",
            rates=_rates(standard="19", reduced="7"),
            rounding_level=RoundingLevel.INVOICE,
            notes="Tax is rounded once per rate on the invoice total.",
        ),
        TaxRegion(
            code="DSF",
            name="Duskfell",
            currency="JPY",
            timezone="Asia/Tokyo",
            rates=_rates(standard="10", reduced="8"),
            prices_include_tax=True,
            rounding=RoundingMode.DOWN,
            notes="Consumer prices include tax; fractions of a yen are "
            "dropped.",
        ),
        TaxRegion(
            code="EMB",
            name="Emberlyn",
            currency="KWD",
            timezone="Asia/Kuwait",
            rates=_rates(standard="5", reduced="2.5"),
            rounding=RoundingMode.HALF_EVEN,
            notes="Banker's rounding to the fils (three places).",
        ),
    )
}
"""Every region, by code."""


def region(code: str) -> TaxRegion:
    """The region for ``code`` (case-insensitive)."""
    try:
        return REGIONS[code.strip().upper()]
    except KeyError:
        raise UnknownRegionError(f"unknown tax region {code!r}") from None


@cache
def _zone(key: str) -> tzinfo:
    # dateutil's bundled zone database, so the tax point does not depend
    # on the host's tz files. Imported lazily: reading it is not free.
    from dateutil.zoneinfo import get_zonefile_instance

    zone = get_zonefile_instance().get(key)
    if zone is None:
        raise UnknownRegionError(f"no time zone data for {key!r}")
    return zone


def local_date(tax_region: TaxRegion, instant: datetime) -> date:
    """The calendar date of ``instant`` in the region's time zone.

    This is the invoice's tax point date: an invoice raised at 23:30 UTC
    for a Duskfell customer is dated the next day.
    """
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("instant must be timezone-aware")
    return instant.astimezone(_zone(tax_region.timezone)).date()
