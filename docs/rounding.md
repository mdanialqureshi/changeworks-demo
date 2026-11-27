# Rounding

Amounts are exact `Decimal`s until they are shown, stored or taxed.
Rounding is always to the currency's minor units: two places for GBP,
EUR and USD, none for JPY, three for KWD.

```python
>>> from decimal import Decimal
>>> from quillstack_billing.money import Money
>>> Money.of("2.345", "GBP").rounded()
Money(amount=Decimal('2.35'), currency=Currency(code='GBP', minor_units=2, symbol='£'))
>>> str(Money.of("1234.5", "JPY").rounded())
'JPY 1,235'

```

## Line amounts and discounts

A line's amount (quantity × unit price, less any line discount) is
rounded half-up. Percentage coupons are rounded half-up too.

## Tax

Each region sets two things:

- **mode**: which way a value exactly halfway between two minor units
  goes;
- **level**: whether tax is rounded on every line and then added up
  (`line`), or added up exactly for each rate and rounded once
  (`invoice`).

| Region | Mode | Level |
|---|---|---|
| Aldermere | half-up | line |
| Brightwater | half-up | line |
| Corvane | half-up | invoice |
| Duskfell | down (fractions of a yen dropped) | line |
| Emberlyn | half-up | line |

Invoice-level rounding can differ from line-level rounding by a minor
unit or two on long invoices; that is expected, and it is what the
Corvane tax office asks for.

```python
>>> from quillstack_billing.rounding import RoundingMode, round_amount
>>> round_amount(Decimal("0.285"), 2, RoundingMode.HALF_UP)
Decimal('0.29')
>>> round_amount(Decimal("13.6"), 0, RoundingMode.DOWN)
Decimal('13')

```
