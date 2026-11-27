from datetime import date

import pytest
from conftest import line

from quillstack_billing.customers import Customer
from quillstack_billing.errors import (
    CurrencyMismatchError,
    InvoiceStateError,
    PaymentError,
)
from quillstack_billing.invoice import Invoice, InvoiceStatus
from quillstack_billing.money import Money
from quillstack_billing.numbering import Numberer
from quillstack_billing.payments import (
    allocate_payment,
    apply_payment,
    instalment_plan,
)
from quillstack_billing.records import Payment, PaymentMethod


def gbp(text: str) -> Money:
    return Money.of(text, "GBP")


def pay(amount: str, day: date = date(2026, 3, 10)) -> Payment:
    return Payment(gbp(amount), day, PaymentMethod.CARD, "ref-1")


def test_partial_then_full_payment(issued_acme_invoice: Invoice) -> None:
    excess = apply_payment(issued_acme_invoice, pay("20.00"))
    assert excess == gbp("0")
    assert issued_acme_invoice.balance_due == gbp("26.48")
    assert issued_acme_invoice.status is InvoiceStatus.PARTIALLY_PAID
    apply_payment(issued_acme_invoice, pay("26.48"))
    assert issued_acme_invoice.balance_due == gbp("0")
    assert issued_acme_invoice.status is InvoiceStatus.PAID


def test_overpayment_is_returned(issued_acme_invoice: Invoice) -> None:
    excess = apply_payment(issued_acme_invoice, pay("50.00"))
    assert excess == gbp("3.52")
    assert issued_acme_invoice.amount_paid == gbp("46.48")
    stored = issued_acme_invoice.payments[0]
    assert (stored.method, stored.reference) == (PaymentMethod.CARD, "ref-1")


def test_settled_invoice_refuses_more(issued_acme_invoice: Invoice) -> None:
    apply_payment(issued_acme_invoice, pay("46.48"))
    with pytest.raises(PaymentError, match="settled"):
        apply_payment(issued_acme_invoice, pay("1"))


def test_payment_rules(acme_invoice: Invoice) -> None:
    with pytest.raises(InvoiceStateError):
        apply_payment(acme_invoice, pay("1"))
    acme_invoice.issue(Numberer(), date(2026, 3, 2))
    with pytest.raises(CurrencyMismatchError):
        apply_payment(
            acme_invoice, Payment(Money.of("1", "EUR"), date(2026, 3, 9))
        )
    with pytest.raises(PaymentError, match="positive"):
        apply_payment(acme_invoice, pay("0"))
    with pytest.raises(PaymentError, match="before"):
        apply_payment(acme_invoice, pay("1", date(2026, 3, 1)))


def _issued(customer: Customer, numberer: Numberer, day: date) -> Invoice:
    invoice = Invoice(customer=customer)
    invoice.add_line(line("Widget", "1", "50.00", "GBP"))  # 60.00 with tax
    invoice.issue(numberer, day)
    return invoice


def test_allocate_oldest_first(acme: Customer) -> None:
    numberer = Numberer()
    newer = _issued(acme, numberer, date(2026, 3, 1))
    older = _issued(acme, numberer, date(2026, 2, 1))
    allocations, left = allocate_payment(
        [newer, older], pay("100.00", date(2026, 3, 5))
    )
    assert [(str(a.number), a.amount) for a in allocations] == [
        ("QS-2026-00002", gbp("60.00")),
        ("QS-2026-00001", gbp("40.00")),
    ]
    assert left == gbp("0")
    assert older.status is InvoiceStatus.PAID
    assert newer.balance_due == gbp("20.00")


def test_allocate_returns_leftover(acme: Customer) -> None:
    invoice = _issued(acme, Numberer(), date(2026, 2, 1))
    allocations, left = allocate_payment([invoice], pay("75.00"))
    assert len(allocations) == 1
    assert left == gbp("15.00")


def test_instalment_plan(issued_acme_invoice: Invoice) -> None:
    plan = instalment_plan(
        issued_acme_invoice, 2, first_due=date(2026, 4, 1), every_days=14
    )
    assert [(i.due, i.amount) for i in plan] == [
        (date(2026, 4, 1), gbp("23.24")),
        (date(2026, 4, 15), gbp("23.24")),
    ]


@pytest.mark.parametrize(("count", "every"), [(0, 30), (3, 0)])
def test_instalment_plan_rejects(
    issued_acme_invoice: Invoice, count: int, every: int
) -> None:
    with pytest.raises(ValueError):
        instalment_plan(
            issued_acme_invoice,
            count,
            first_due=date(2026, 4, 1),
            every_days=every,
        )
