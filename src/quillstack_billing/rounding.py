"""Rounding modes and helpers.

Quillstack rounds money to the currency's minor units. Which way a half
unit goes depends on the tax region (see ``docs/rounding.md``), so the
mode is always explicit: nothing here relies on the ambient
:mod:`decimal` context.
"""

from decimal import (
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Decimal,
)
from enum import StrEnum


class RoundingMode(StrEnum):
    """How a value exactly between two minor units is rounded."""

    HALF_UP = "half-up"
    HALF_EVEN = "half-even"
    DOWN = "down"
    UP = "up"


class RoundingLevel(StrEnum):
    """Where tax is rounded: on every line, or once per invoice."""

    LINE = "line"
    INVOICE = "invoice"


DECIMAL_ROUNDING: dict[RoundingMode, str] = {
    RoundingMode.HALF_UP: ROUND_HALF_UP,
    RoundingMode.HALF_EVEN: ROUND_HALF_EVEN,
    RoundingMode.DOWN: ROUND_DOWN,
    RoundingMode.UP: ROUND_UP,
}
"""The :mod:`decimal` constant for each :class:`RoundingMode`."""


def minor_unit(minor_units: int) -> Decimal:
    """The smallest amount for a currency with ``minor_units`` digits.

    >>> minor_unit(2)
    Decimal('0.01')
    >>> minor_unit(0)
    Decimal('1')
    """
    if minor_units < 0:
        raise ValueError("minor_units must not be negative")
    return Decimal(1).scaleb(-minor_units)


def round_amount(
    amount: Decimal, minor_units: int, mode: RoundingMode
) -> Decimal:
    """``amount`` rounded to ``minor_units`` decimal places using ``mode``.

    >>> round_amount(Decimal("2.345"), 2, RoundingMode.HALF_UP)
    Decimal('2.35')
    >>> round_amount(Decimal("2.345"), 2, RoundingMode.HALF_EVEN)
    Decimal('2.34')
    """
    return amount.quantize(
        minor_unit(minor_units), rounding=DECIMAL_ROUNDING[mode]
    )
