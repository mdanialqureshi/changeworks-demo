from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from quillstack_billing.errors import UnknownRegionError
from quillstack_billing.regions import (
    REGIONS,
    TaxCategory,
    local_date,
    region,
)
from quillstack_billing.rounding import RoundingLevel, RoundingMode


def test_every_region_is_keyed_by_its_code() -> None:
    assert sorted(REGIONS) == ["ALD", "BRW", "CRV", "DSF", "EMB"]
    for code, tax_region in REGIONS.items():
        assert tax_region.code == code


def test_lookup_is_case_insensitive() -> None:
    assert region(" ald ").name == "Aldermere"


def test_unknown_region() -> None:
    with pytest.raises(UnknownRegionError):
        region("ZZZ")


def test_rates() -> None:
    ald = region("ALD")
    assert ald.rate(TaxCategory.STANDARD) == Decimal("20")
    assert ald.rate("reduced") == Decimal("5")
    assert ald.rate(TaxCategory.ZERO) == 0
    assert ald.rate(TaxCategory.EXEMPT) == 0


def test_region_settings() -> None:
    assert region("DSF").prices_include_tax
    assert region("DSF").rounding is RoundingMode.DOWN
    assert region("EMB").rounding is RoundingMode.HALF_EVEN
    assert region("CRV").rounding_level is RoundingLevel.INVOICE
    assert region("ALD").rounding_level is RoundingLevel.LINE


def test_rates_are_read_only() -> None:
    with pytest.raises(TypeError):
        region("ALD").rates[TaxCategory.STANDARD] = Decimal(0)  # type: ignore


def test_local_date_crosses_midnight_east() -> None:
    late = datetime(2026, 3, 31, 23, 30, tzinfo=UTC)
    assert local_date(region("DSF"), late) == date(2026, 4, 1)
    assert local_date(region("ALD"), late) == date(2026, 4, 1)  # BST


def test_local_date_west_of_utc() -> None:
    early = datetime(2026, 1, 15, 3, 0, tzinfo=UTC)
    assert local_date(region("BRW"), early) == date(2026, 1, 14)


def test_local_date_accepts_any_offset() -> None:
    plus_two = timezone(timedelta(hours=2))
    instant = datetime(2026, 7, 1, 0, 30, tzinfo=plus_two)
    assert local_date(region("ALD"), instant) == date(2026, 6, 30)


def test_local_date_needs_an_aware_instant() -> None:
    with pytest.raises(ValueError):
        local_date(region("ALD"), datetime(2026, 1, 1, 12, 0))
