"""Coupons and how they combine.

The rules (also in ``docs/discounts.md``):

1. A coupon must be valid on the invoice's issue date, and the invoice
   subtotal must reach the coupon's ``min_subtotal`` (checked against
   the subtotal before any discount).
2. A coupon that is not ``stackable`` must be the only coupon.
3. Coupons apply in ``priority`` order, lowest first. Within the same
   priority, percentage coupons apply before fixed-amount coupons, so a
   percentage is always taken from the larger amount.
4. Each discount is taken from what is left after the previous ones and
   never takes the total below zero.
5. Percentage discounts are rounded half-up to the currency's minor
   units.
"""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from .errors import CouponError, NotFoundError
from .money import Money, currency, to_decimal

HUNDRED = Decimal(100)


class DiscountKind(StrEnum):
    AMOUNT = "amount"
    PERCENT = "percent"


@dataclass(frozen=True)
class Coupon:
    """A discount code.

    ``value`` is a percentage for ``percent`` coupons and an amount in
    ``currency`` for ``amount`` coupons.
    """

    code: str
    kind: DiscountKind
    value: Decimal
    currency: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    min_subtotal: Decimal | None = None
    max_redemptions: int | None = None
    stackable: bool = True
    priority: int = 100

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", self.code.strip().upper())
        object.__setattr__(self, "kind", DiscountKind(self.kind))
        object.__setattr__(self, "value", to_decimal(self.value))
        if not self.code.isalnum():
            raise ValueError(f"coupon code must be alphanumeric: {self.code}")
        if self.value <= 0:
            raise ValueError("a coupon's value must be positive")
        if self.kind is DiscountKind.PERCENT:
            if self.value > HUNDRED:
                raise ValueError("a percentage coupon cannot exceed 100")
            if self.currency is not None:
                raise ValueError("percentage coupons have no currency")
        else:
            if self.currency is None:
                raise ValueError("amount coupons need a currency")
            object.__setattr__(self, "currency", currency(self.currency).code)
        if self.min_subtotal is not None:
            object.__setattr__(
                self, "min_subtotal", to_decimal(self.min_subtotal)
            )
        if (
            self.valid_from
            and self.valid_until
            and self.valid_until < self.valid_from
        ):
            raise ValueError("valid_until is before valid_from")
        if self.max_redemptions is not None and self.max_redemptions < 1:
            raise ValueError("max_redemptions must be at least 1")

    def is_valid_on(self, day: date) -> bool:
        if self.valid_from is not None and day < self.valid_from:
            return False
        return self.valid_until is None or day <= self.valid_until

    def discount_on(self, remaining: Money) -> Money:
        """The discount this coupon gives on ``remaining``."""
        if self.kind is DiscountKind.PERCENT:
            off = (remaining * self.value / HUNDRED).rounded()
        else:
            off = Money.of(self.value, self.currency or "")
        return min(off, remaining)


@dataclass(frozen=True)
class AppliedDiscount:
    """One coupon's effect on an invoice."""

    code: str
    amount: Money


def check_combination(coupons: Sequence[Coupon]) -> None:
    """Refuse duplicate codes and non-stackable coupons with others."""
    codes = [c.code for c in coupons]
    if len(set(codes)) != len(codes):
        raise CouponError("the same coupon was given twice")
    if len(coupons) > 1 and any(not c.stackable for c in coupons):
        lone = next(c.code for c in coupons if not c.stackable)
        raise CouponError(f"{lone} cannot be combined with other coupons")


def apply_coupons(
    subtotal: Money, coupons: Sequence[Coupon], on: date
) -> list[AppliedDiscount]:
    """The discounts ``coupons`` give on ``subtotal``, in the order they
    apply. See the module docstring for the rules."""
    check_combination(coupons)
    for coupon in coupons:
        if not coupon.is_valid_on(on):
            raise CouponError(f"{coupon.code} is not valid on {on}")
        if coupon.currency not in (None, subtotal.currency.code):
            raise CouponError(
                f"{coupon.code} is in {coupon.currency}, "
                f"the invoice in {subtotal.currency}"
            )
        if (
            coupon.min_subtotal is not None
            and subtotal.amount < coupon.min_subtotal
        ):
            raise CouponError(
                f"{coupon.code} needs a subtotal of at least "
                f"{coupon.min_subtotal}"
            )
    remaining = subtotal
    applied = []
    for coupon in sorted(coupons, key=lambda c: (c.priority, c.kind)):
        off = coupon.discount_on(remaining)
        remaining = remaining - off
        applied.append(AppliedDiscount(coupon.code, off))
    return applied


class CouponBook:
    """Known coupons and how many times each has been redeemed."""

    def __init__(
        self,
        coupons: Iterable[Coupon] = (),
        redemptions: dict[str, int] | None = None,
    ) -> None:
        self._coupons = {c.code: c for c in coupons}
        self._redemptions = dict(redemptions or {})

    def add(self, coupon: Coupon) -> None:
        if coupon.code in self._coupons:
            raise CouponError(f"coupon {coupon.code} already exists")
        self._coupons[coupon.code] = coupon

    def get(self, code: str) -> Coupon:
        try:
            return self._coupons[code.strip().upper()]
        except KeyError:
            raise NotFoundError(f"no coupon {code}") from None

    def redemptions(self, code: str) -> int:
        return self._redemptions.get(self.get(code).code, 0)

    def redeem(self, code: str) -> Coupon:
        """Count one use of ``code``; refuse it once it is used up."""
        coupon = self.get(code)
        used = self._redemptions.get(coupon.code, 0)
        if coupon.max_redemptions is not None and used >= (
            coupon.max_redemptions
        ):
            raise CouponError(f"{coupon.code} has been used up")
        self._redemptions[coupon.code] = used + 1
        return coupon

    def __iter__(self) -> Iterator[Coupon]:
        return iter(self._coupons.values())

    def state(self) -> dict[str, int]:
        return dict(self._redemptions)
