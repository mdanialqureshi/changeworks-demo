# Coupons and discounts

There are two kinds of discount:

- a **line discount** (`DISCOUNT%` on a line), applied to that line
  only, before anything else;
- **coupons**, applied to the invoice subtotal.

## How coupons combine

1. A coupon must be valid on the invoice's issue date, and the
   subtotal (before any coupon) must reach the coupon's minimum
   subtotal, if it has one.
2. A coupon marked "no stack" must be the only coupon on the invoice.
3. Coupons apply in priority order, lowest number first (the default
   priority is 100). Within the same priority, **percentage coupons
   apply before fixed-amount coupons**, so a percentage is always taken
   from the larger amount.
4. Each coupon is taken from what is left after the previous ones; the
   total never goes below zero.
5. Percentage discounts are rounded half-up to the currency's minor
   units.

Coupons with a maximum number of redemptions are counted when an
invoice using them is issued.

## Tax on discounted invoices

The coupon total is shared across the invoice lines in proportion to
their amounts (the last line takes any rounding remainder), and tax is
worked out on the discounted line amounts. So a coupon reduces the tax
as well as the price.

```python
>>> from datetime import date
>>> from decimal import Decimal
>>> from quillstack_billing.discounts import Coupon, apply_coupons
>>> from quillstack_billing.money import Money
>>> spring = Coupon("SPRING", "percent", Decimal(10))
>>> [d.amount for d in apply_coupons(Money.of("39.95", "GBP"), [spring], date(2026, 3, 2))]
[Money(amount=Decimal('4.00'), currency=Currency(code='GBP', minor_units=2, symbol='£'))]

```
