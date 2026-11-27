from datetime import date
from decimal import Decimal

import pytest
from conftest import line

from quillstack_billing.customers import Customer
from quillstack_billing.discounts import Coupon, DiscountKind
from quillstack_billing.errors import CouponError, InvoiceStateError
from quillstack_billing.invoice import (
    Invoice,
    InvoiceStatus,
    LineItem,
    spread,
)
from quillstack_billing.money import Money
from quillstack_billing.numbering import Numberer
from quillstack_billing.regions import TaxCategory


def gbp(text: str) -> Money:
    return Money.of(text, "GBP")


def test_line_amount_applies_line_discount() -> None:
    item = line("Widget", "3", "9.99", "GBP", discount="10")
    assert item.amount == gbp("26.97")  # 29.97 * 0.9 = 26.973


def test_fractional_quantities() -> None:
    assert line("Consulting", "1.5", "80.00", "GBP").amount == gbp("120.00")


@pytest.mark.parametrize(
    ("quantity", "price", "discount"),
    [("0", "1", "0"), ("-1", "1", "0"), ("1", "-1", "0"), ("1", "1", "101")],
)
def test_invalid_lines(quantity: str, price: str, discount: str) -> None:
    with pytest.raises(ValueError):
        line("X", quantity, price, "GBP", discount=discount)


def test_line_needs_description() -> None:
    with pytest.raises(ValueError):
        LineItem(" ", Decimal(1), gbp("1"))


def test_totals_exclusive_region(acme_invoice: Invoice) -> None:
    totals = acme_invoice.totals()
    assert totals.subtotal == gbp("39.98")
    assert totals.discount == gbp("0")
    assert totals.tax == gbp("6.50")
    assert totals.total == gbp("46.48")
    assert totals.net == gbp("39.98")


def test_coupon_is_spread_across_rates(acme_invoice: Invoice) -> None:
    acme_invoice.add_coupon(Coupon("TEN", DiscountKind.PERCENT, Decimal(10)))
    totals = acme_invoice.totals()
    assert totals.discount == gbp("4.00")
    # 30.00 - 3.00 at 20% = 5.40; 9.98 - 1.00 at 5% = 0.449 -> 0.45
    assert totals.tax == gbp("5.85")
    assert totals.total == gbp("41.83")


def test_inclusive_region_total_is_the_sum_of_lines(kumo: Customer) -> None:
    invoice = Invoice(customer=kumo)
    invoice.add_line(line("Notebook", "3", "1100", "JPY"))
    invoice.add_line(line("Tea", "2", "540", "JPY", TaxCategory.REDUCED))
    totals = invoice.totals()
    assert totals.total == Money.of("4380", "JPY")
    assert totals.tax == Money.of("380", "JPY")
    assert totals.net == Money.of("4000", "JPY")


def test_tax_exempt_customer(acme: Customer) -> None:
    exempt = Customer(
        "C-0009", "Charity", "fin@charity.example", "ALD", tax_exempt=True
    )
    invoice = Invoice(customer=exempt)
    invoice.add_line(line("Widget", "1", "10", "GBP"))
    assert invoice.totals().total == gbp("10")


def test_lines_must_match_customer_currency(acme_invoice: Invoice) -> None:
    with pytest.raises(InvoiceStateError, match="EUR"):
        acme_invoice.add_line(line("X", "1", "1", "EUR"))


def test_invalid_coupon_is_not_kept(acme_invoice: Invoice) -> None:
    coupon = Coupon(
        "BULK", DiscountKind.PERCENT, Decimal(5), min_subtotal=Decimal(500)
    )
    with pytest.raises(CouponError):
        acme_invoice.add_coupon(coupon)
    assert acme_invoice.coupons == []


def test_issue_numbers_and_dates(
    acme_invoice: Invoice, numberer: Numberer
) -> None:
    assert acme_invoice.status is InvoiceStatus.DRAFT
    assert acme_invoice.due_date is None
    number = acme_invoice.issue(numberer, date(2026, 3, 2))
    assert str(number) == "QS-2026-00001"
    assert acme_invoice.issue_date == date(2026, 3, 2)
    assert acme_invoice.due_date == date(2026, 4, 1)
    assert acme_invoice.status is InvoiceStatus.ISSUED


def test_issued_invoices_are_frozen(issued_acme_invoice: Invoice) -> None:
    with pytest.raises(InvoiceStateError):
        issued_acme_invoice.add_line(line("More", "1", "1", "GBP"))
    with pytest.raises(InvoiceStateError):
        issued_acme_invoice.issue(Numberer(), date(2026, 3, 3))


def test_cannot_issue_empty_invoice(acme: Customer) -> None:
    with pytest.raises(InvoiceStateError, match="no lines"):
        Invoice(customer=acme).issue(Numberer(), date(2026, 1, 1))


def test_expired_coupon_blocks_issue(
    acme_invoice: Invoice, numberer: Numberer
) -> None:
    acme_invoice.add_coupon(
        Coupon(
            "FEB",
            DiscountKind.PERCENT,
            Decimal(5),
            valid_until=date(2026, 12, 31),
        )
    )
    with pytest.raises(CouponError):
        acme_invoice.issue(numberer, date(2027, 1, 4))
    assert acme_invoice.number is None


def test_invoice_terms_override_customer_terms(acme: Customer) -> None:
    from quillstack_billing.terms import PaymentTerms

    invoice = Invoice(customer=acme, terms=PaymentTerms.parse("net-7"))
    invoice.add_line(line("Widget", "1", "1", "GBP"))
    invoice.issue(Numberer(), date(2026, 3, 2))
    assert invoice.due_date == date(2026, 3, 9)


def test_days_overdue(issued_acme_invoice: Invoice) -> None:
    assert issued_acme_invoice.days_overdue(date(2026, 3, 20)) == 0
    assert issued_acme_invoice.days_overdue(date(2026, 4, 1)) == 0
    assert issued_acme_invoice.days_overdue(date(2026, 4, 11)) == 10


def test_spread_puts_the_remainder_on_the_last_line() -> None:
    shares = spread(gbp("1.00"), [gbp("1"), gbp("1"), gbp("1")])
    assert shares == [gbp("0.33"), gbp("0.33"), gbp("0.34")]
    assert spread(gbp("1"), []) == []
    assert spread(gbp("1"), [gbp("0")]) == [gbp("0")]
