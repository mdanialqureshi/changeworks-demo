from datetime import date

import pytest

from quillstack_billing.credit_notes import issue_credit_note, total_credited
from quillstack_billing.errors import CreditNoteError
from quillstack_billing.invoice import Invoice, InvoiceStatus
from quillstack_billing.money import Money
from quillstack_billing.numbering import DocumentKind, Numberer
from quillstack_billing.payments import apply_payment
from quillstack_billing.records import Payment


def gbp(text: str) -> Money:
    return Money.of(text, "GBP")


ON = date(2026, 3, 12)


def test_credit_reduces_balance(issued_acme_invoice: Invoice) -> None:
    note = issue_credit_note(
        issued_acme_invoice,
        gbp("6.48"),
        numberer=Numberer(),
        on=ON,
        reason="  damaged in transit ",
    )
    assert note.number.kind is DocumentKind.CREDIT_NOTE
    assert note.invoice_number == issued_acme_invoice.number
    assert note.reason == "damaged in transit"
    assert issued_acme_invoice.amount_credited == gbp("6.48")
    assert issued_acme_invoice.balance_due == gbp("40.00")
    assert issued_acme_invoice.status is InvoiceStatus.PARTIALLY_PAID


def test_full_credit_settles(issued_acme_invoice: Invoice) -> None:
    issue_credit_note(
        issued_acme_invoice, gbp("46.48"), numberer=Numberer(), on=ON
    )
    assert issued_acme_invoice.status is InvoiceStatus.PAID


def test_cannot_credit_more_than_balance(
    issued_acme_invoice: Invoice,
) -> None:
    apply_payment(issued_acme_invoice, Payment(gbp("40.00"), date(2026, 3, 5)))
    with pytest.raises(CreditNoteError, match="more than"):
        issue_credit_note(
            issued_acme_invoice, gbp("6.49"), numberer=Numberer(), on=ON
        )
    assert issued_acme_invoice.credit_notes == []


def test_credit_note_rules(acme_invoice: Invoice) -> None:
    with pytest.raises(CreditNoteError, match="issued"):
        issue_credit_note(acme_invoice, gbp("1"), numberer=Numberer(), on=ON)
    acme_invoice.issue(Numberer(), date(2026, 3, 2))
    with pytest.raises(CreditNoteError, match="positive"):
        issue_credit_note(acme_invoice, gbp("0"), numberer=Numberer(), on=ON)
    with pytest.raises(CreditNoteError, match="before"):
        issue_credit_note(
            acme_invoice, gbp("1"), numberer=Numberer(), on=date(2026, 3, 1)
        )


def test_total_credited(issued_acme_invoice: Invoice) -> None:
    numberer = Numberer()
    notes = [
        issue_credit_note(
            issued_acme_invoice, gbp(a), numberer=numberer, on=ON
        )
        for a in ("1.00", "2.50")
    ]
    assert total_credited(notes, issued_acme_invoice) == gbp("3.50")
