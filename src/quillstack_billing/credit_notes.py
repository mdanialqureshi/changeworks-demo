"""Credit notes: reducing what an issued invoice asks for.

A credit note is numbered in its own ``CN-`` sequence, refers to one
issued invoice, is in that invoice's currency, and cannot credit more
than the invoice's balance due.
"""

from datetime import date

from .errors import CreditNoteError
from .invoice import Invoice
from .money import Money
from .numbering import DocumentKind, Numberer
from .records import CreditNote


def issue_credit_note(
    invoice: Invoice,
    amount: Money,
    *,
    numberer: Numberer,
    on: date,
    reason: str = "",
) -> CreditNote:
    """Credit ``amount`` against ``invoice`` and return the note."""
    if invoice.is_draft or invoice.number is None:
        raise CreditNoteError("only an issued invoice can be credited")
    if not amount.amount > 0:
        raise CreditNoteError("a credit note must be a positive amount")
    if invoice.issue_date and on < invoice.issue_date:
        raise CreditNoteError("credit note is dated before the invoice")
    if amount > invoice.balance_due:
        raise CreditNoteError(
            f"{amount} is more than the balance due on {invoice.number}"
        )
    note = CreditNote(
        number=numberer.next(DocumentKind.CREDIT_NOTE, on),
        invoice_number=invoice.number,
        amount=amount,
        issued_on=on,
        reason=reason.strip(),
    )
    invoice.credit_notes.append(note)
    return note


def total_credited(notes: list[CreditNote], invoice: Invoice) -> Money:
    """The sum of the notes that refer to ``invoice``."""
    return sum(
        (n.amount for n in notes if n.invoice_number == invoice.number),
        Money.zero(invoice.currency),
    )
