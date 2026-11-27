from datetime import date
from decimal import Decimal

import pytest

from quillstack_billing.discounts import (
    Coupon,
    CouponBook,
    DiscountKind,
    apply_coupons,
)
from quillstack_billing.errors import CouponError, NotFoundError
from quillstack_billing.money import Money

DAY = date(2026, 3, 2)
PCT, AMT = DiscountKind.PERCENT, DiscountKind.AMOUNT


def gbp(text: str) -> Money:
    return Money.of(text, "GBP")


def amounts(subtotal: str, *coupons: Coupon) -> list[tuple[str, Money]]:
    return [
        (d.code, d.amount) for d in apply_coupons(gbp(subtotal), coupons, DAY)
    ]


def test_percentage_coupon_rounds_half_up() -> None:
    # 10% of 39.95 is 3.995
    assert amounts("39.95", Coupon("TEN", PCT, Decimal(10))) == [
        ("TEN", gbp("4.00"))
    ]


def test_amount_coupon() -> None:
    coupon = Coupon("FIVER", AMT, Decimal(5), currency="GBP")
    assert amounts("20", coupon) == [("FIVER", gbp("5"))]


def test_discount_never_goes_below_zero() -> None:
    coupon = Coupon("BIG", AMT, Decimal(50), currency="GBP")
    assert amounts("20", coupon) == [("BIG", gbp("20"))]


def test_codes_are_normalised() -> None:
    assert Coupon(" spring26 ", PCT, Decimal(5)).code == "SPRING26"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"code": "NO-DASH", "kind": PCT, "value": Decimal(5)},
        {"code": "ZERO", "kind": PCT, "value": Decimal(0)},
        {"code": "HUGE", "kind": PCT, "value": Decimal(101)},
        {"code": "PCTCUR", "kind": PCT, "value": 5, "currency": "GBP"},
        {"code": "NOCUR", "kind": AMT, "value": Decimal(5)},
        {
            "code": "BACKWARDS",
            "kind": PCT,
            "value": Decimal(5),
            "valid_from": date(2026, 2, 1),
            "valid_until": date(2026, 1, 1),
        },
        {"code": "NEVER", "kind": PCT, "value": 5, "max_redemptions": 0},
    ],
)
def test_invalid_coupons(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        Coupon(**kwargs)  # type: ignore[arg-type]


def test_validity_window() -> None:
    coupon = Coupon(
        "MARCH",
        PCT,
        Decimal(5),
        valid_from=date(2026, 3, 1),
        valid_until=date(2026, 3, 31),
    )
    assert coupon.is_valid_on(date(2026, 3, 1))
    assert coupon.is_valid_on(date(2026, 3, 31))
    assert not coupon.is_valid_on(date(2026, 4, 1))
    with pytest.raises(CouponError, match="not valid"):
        apply_coupons(gbp("10"), [coupon], date(2026, 2, 28))


def test_minimum_subtotal_is_enforced() -> None:
    coupon = Coupon("BULK", PCT, Decimal(5), min_subtotal=Decimal(100))
    with pytest.raises(CouponError, match="at least"):
        amounts("99.99", coupon)
    assert amounts("100", coupon) == [("BULK", gbp("5.00"))]


def test_coupon_currency_must_match() -> None:
    coupon = Coupon("EURO", AMT, Decimal(5), currency="EUR")
    with pytest.raises(CouponError, match="EUR"):
        amounts("10", coupon)


def test_non_stackable_coupon_must_be_alone() -> None:
    solo = Coupon("SOLO", PCT, Decimal(20), stackable=False)
    other = Coupon("OTHER", PCT, Decimal(5))
    assert amounts("10", solo) == [("SOLO", gbp("2.00"))]
    with pytest.raises(CouponError, match="SOLO"):
        amounts("10", solo, other)


def test_same_coupon_twice_is_refused() -> None:
    coupon = Coupon("TEN", PCT, Decimal(10))
    with pytest.raises(CouponError):
        amounts("10", coupon, coupon)


def test_priority_order_for_percentages() -> None:
    first = Coupon("FIRST", PCT, Decimal(50), priority=1)
    second = Coupon("SECOND", PCT, Decimal(10), priority=2)
    # 50% of 100 = 50, then 10% of 50 = 5, whatever order they are given
    expected = [("FIRST", gbp("50.00")), ("SECOND", gbp("5.00"))]
    assert amounts("100", second, first) == expected
    assert amounts("100", first, second) == expected


def test_priority_order_for_amounts() -> None:
    first = Coupon("FIRST", AMT, Decimal(8), currency="GBP", priority=1)
    second = Coupon("SECOND", AMT, Decimal(5), currency="GBP", priority=9)
    assert amounts("10", second, first) == [
        ("FIRST", gbp("8")),
        ("SECOND", gbp("2")),
    ]


def test_coupon_book_redemptions() -> None:
    book = CouponBook([Coupon("ONCE", PCT, Decimal(5), max_redemptions=1)])
    assert book.redemptions("once") == 0
    book.redeem("once")
    assert book.redemptions("ONCE") == 1
    with pytest.raises(CouponError, match="used up"):
        book.redeem("ONCE")
    with pytest.raises(NotFoundError):
        book.get("NOPE")


def test_coupon_book_refuses_duplicates() -> None:
    book = CouponBook([Coupon("A1", PCT, Decimal(5))])
    with pytest.raises(CouponError):
        book.add(Coupon("A1", PCT, Decimal(7)))
    assert [c.code for c in book] == ["A1"]
