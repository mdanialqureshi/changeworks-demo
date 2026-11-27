"""Money: an exact :class:`~decimal.Decimal` amount in one currency.

Amounts are never floats. Arithmetic keeps full precision; rounding to
the currency's minor units happens only when asked for, with an
explicit :class:`~quillstack_billing.rounding.RoundingMode`.

>>> price = Money.of("19.99", "GBP")
>>> str(price * 3)
'GBP 59.97'
>>> (price + Money.of("0.01", "GBP")).format()
'£20.00'
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from functools import total_ordering
from typing import Self

from .errors import CurrencyMismatchError, UnknownCurrencyError
from .rounding import RoundingMode, minor_unit, round_amount


@dataclass(frozen=True, slots=True)
class Currency:
    """An ISO 4217 currency and how many minor units it has."""

    code: str
    minor_units: int
    symbol: str

    @property
    def exponent(self) -> Decimal:
        """The smallest representable amount, e.g. ``0.01``."""
        return minor_unit(self.minor_units)

    def __str__(self) -> str:
        return self.code


CURRENCIES: dict[str, Currency] = {
    c.code: c
    for c in (
        Currency("GBP", 2, "£"),
        Currency("EUR", 2, "€"),
        Currency("USD", 2, "$"),
        Currency("JPY", 0, "¥"),
        Currency("KWD", 3, "KD "),
    )
}
"""Currencies Quillstack invoices in, by code."""


def currency(code: str | Currency) -> Currency:
    """The :class:`Currency` for ``code`` (case-insensitive)."""
    if isinstance(code, Currency):
        return code
    try:
        return CURRENCIES[code.strip().upper()]
    except KeyError:
        raise UnknownCurrencyError(f"unknown currency {code!r}") from None


def to_decimal(value: Decimal | int | str) -> Decimal:
    """``value`` as a finite Decimal; floats and bools are refused."""
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(f"use a str or Decimal, not {type(value).__name__}")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, str):
        try:
            result = Decimal(value.strip().replace(",", ""))
        except InvalidOperation:
            raise ValueError(f"not a number: {value!r}") from None
    else:
        raise TypeError(f"cannot make a Decimal from {type(value).__name__}")
    if not result.is_finite():
        raise ValueError(f"amount must be finite, got {value!r}")
    return result


@total_ordering
@dataclass(frozen=True, slots=True)
class Money:
    """An amount of one currency.

    Adding, subtracting or comparing two amounts in different currencies
    raises :class:`CurrencyMismatchError`. Multiplying by a number keeps
    full precision; call :meth:`rounded` to get minor units.
    """

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", to_decimal(self.amount))
        object.__setattr__(self, "currency", currency(self.currency))

    @classmethod
    def of(cls, amount: Decimal | int | str, code: str | Currency) -> Self:
        """``Money.of("12.50", "GBP")``."""
        return cls(to_decimal(amount), currency(code))

    @classmethod
    def zero(cls, code: str | Currency) -> Self:
        """Zero in the given currency."""
        return cls(Decimal(0), currency(code))

    # -- arithmetic -------------------------------------------------------

    def _check(self, other: Money) -> None:
        if other.currency != self.currency:
            raise CurrencyMismatchError(
                f"cannot combine {self.currency} and {other.currency}"
            )

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._check(other)
        return Money(self.amount + other.amount, self.currency)

    def __radd__(self, other: object) -> Money:
        # Lets sum() start from the integer 0.
        if other == 0:
            return self
        return NotImplemented

    def __sub__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._check(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __abs__(self) -> Money:
        return Money(abs(self.amount), self.currency)

    def __mul__(self, factor: object) -> Money:
        if isinstance(factor, Money | float | bool):
            return NotImplemented
        if not isinstance(factor, Decimal | int):
            return NotImplemented
        return Money(self.amount * factor, self.currency)

    __rmul__ = __mul__

    def __truediv__(self, divisor: object) -> Money:
        if isinstance(divisor, Money | float | bool):
            return NotImplemented
        if not isinstance(divisor, Decimal | int):
            return NotImplemented
        return Money(self.amount / divisor, self.currency)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount < other.amount

    # -- queries ----------------------------------------------------------

    @property
    def is_zero(self) -> bool:
        return self.amount == 0

    @property
    def is_negative(self) -> bool:
        return self.amount < 0

    def rounded(self, mode: RoundingMode = RoundingMode.HALF_UP) -> Money:
        """This amount rounded to the currency's minor units."""
        return Money(
            round_amount(self.amount, self.currency.minor_units, mode),
            self.currency,
        )

    def allocate(self, ratios: Sequence[int | Decimal]) -> list[Money]:
        """Split this amount by ``ratios`` without losing a minor unit.

        The shares are rounded down to minor units; the units left over
        go one each to the first shares, so the shares always add up to
        the (rounded) amount.
        """
        weights = [to_decimal(r) for r in ratios]
        if not weights or any(w < 0 for w in weights) or sum(weights) == 0:
            raise ValueError("ratios must be non-negative and not all zero")
        if self.is_negative:
            raise ValueError("cannot allocate a negative amount")
        total = sum(weights)
        unit = self.currency.exponent
        return [
            Money(
                (self.amount * w / total).quantize(unit, rounding=ROUND_DOWN),
                self.currency,
            )
            for w in weights
        ]

    # -- display ----------------------------------------------------------

    def _digits(self) -> str:
        places = self.currency.minor_units
        return f"{self.rounded().amount:,.{places}f}"

    def plain(self) -> str:
        """The rounded amount with no grouping, e.g. ``1234.50``."""
        return f"{self.rounded().amount:.{self.currency.minor_units}f}"

    def format(self) -> str:
        """The amount with the currency symbol, e.g. ``£1,234.50``."""
        sign = "-" if self.is_negative else ""
        return f"{sign}{self.currency.symbol}{abs(self)._digits()}"

    def __str__(self) -> str:
        return f"{self.currency.code} {self._digits()}"


def sum_money(values: Iterable[Money], code: str | Currency) -> Money:
    """The total of ``values``, all of which must be in ``code``."""
    total = Money.zero(code)
    for value in values:
        total = total + value
    return total
