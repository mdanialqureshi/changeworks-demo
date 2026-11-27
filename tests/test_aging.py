from datetime import date

import pytest
from conftest import line

from quillstack_billing.aging import (
    BUCKETS,
    aging_report,
    bucket_for,
    format_report,
)
from quillstack_billing.customers import Customer
from quillstack_billing.invoice import Invoice
from quillstack_billing.money import Money
from quillstack_billing.numbering import Numberer
from quillstack_billing.payments import apply_payment
from quillstack_billing.records import Payment

AS_OF = date(2026, 3, 17)


@pytest.mark.parametrize(
    ("days", "bucket"),
    [(0, "current"), (1, "1-30"), (10, "1-30"), (45, "31-60")]
    + [(75, "61-90"), (91, "90+"), (400, "90+")],
)
def test_bucket_for(days: int, bucket: str) -> None:
    assert bucket_for(days) == bucket


def test_bucket_for_rejects_negative_days() -> None:
    with pytest.raises(ValueError):
        bucket_for(-1)


def issued(
    customer: Customer, numberer: Numberer, day: date, price: str
) -> Invoice:
    invoice = Invoice(customer=customer)
    invoice.add_line(line("Widget", "1", price, customer.currency))
    invoice.issue(numberer, day)
    return invoice


def test_report_groups_by_customer_and_currency(
    acme: Customer, bruecke: Customer
) -> None:
    numberer = Numberer()
    invoices = [
        issued(acme, numberer, date(2026, 1, 1), "100.00"),  # 45 days
        issued(acme, numberer, date(2026, 3, 1), "10.00"),  # current
        issued(bruecke, numberer, date(2025, 11, 1), "100.00"),  # 106
    ]
    report = aging_report(invoices, AS_OF)
    assert [(r.customer_id, r.currency) for r in report.rows] == [
        ("C-0002", "EUR"),
        ("C-0001", "GBP"),
    ]
    acme_row = report.rows[1]
    assert acme_row.buckets["31-60"] == Money.of("120.00", "GBP")
    assert acme_row.buckets["current"] == Money.of("12.00", "GBP")
    assert acme_row.total == Money.of("132.00", "GBP")
    totals = report.totals()
    assert totals["EUR"]["90+"] == Money.of("119.00", "EUR")
    assert set(totals["GBP"]) == set(BUCKETS)


def test_report_skips_paid_drafts_and_future(acme: Customer) -> None:
    numberer = Numberer()
    paid = issued(acme, numberer, date(2026, 1, 1), "10.00")
    apply_payment(paid, Payment(Money.of("12.00", "GBP"), date(2026, 1, 9)))
    draft = Invoice(customer=acme)
    draft.add_line(line("Widget", "1", "1", "GBP"))
    future = issued(acme, numberer, date(2026, 4, 1), "10.00")
    assert aging_report([paid, draft, future], AS_OF).rows == []


def test_report_currency_filter(acme: Customer, bruecke: Customer) -> None:
    numberer = Numberer()
    invoices = [
        issued(acme, numberer, date(2026, 1, 1), "1.00"),
        issued(bruecke, numberer, date(2026, 1, 1), "1.00"),
    ]
    report = aging_report(invoices, AS_OF, "eur")
    assert [r.currency for r in report.rows] == ["EUR"]


def test_format_report(acme: Customer) -> None:
    report = aging_report(
        [issued(acme, Numberer(), date(2026, 1, 1), "100.00")], AS_OF
    )
    text = format_report(report)
    assert text.splitlines()[0] == "Aging as of 2026-03-17"
    assert "GBP" in text
    assert "C-0001" in text
    assert text.splitlines()[-1].startswith("TOTAL")
    assert "120.00" in text.splitlines()[-1]


def test_format_empty_report() -> None:
    text = format_report(aging_report([], AS_OF))
    assert text.endswith("No open invoices.")
