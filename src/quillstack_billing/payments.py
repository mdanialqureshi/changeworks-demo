"""Applying payments to invoices, and instalment plans.

A payment never takes an invoice's balance below zero: anything over
the balance is returned to the caller as unapplied money (the CLI
reports it as customer credit).
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, timedelta

from .errors import CurrencyMismatchError, InvoiceStateError, PaymentError
from .invoice import Invoice
from .money import Money
from .numbering import DocumentNumber
from .records import Payment


def apply_payment(invoice: Invoice, payment: Payment) -> Money:
    """Record ``payment`` against ``invoice``; return the unapplied part.

    The payment stored on the invoice is the applied amount; the
    reference, method and date are kept.
    """
    if invoice.is_draft:
        raise InvoiceStateError("cannot pay a draft invoice")
    if payment.amount.currency != invoice.currency:
        raise CurrencyMismatchError(
            f"payment in {payment.amount.currency}, "
            f"{invoice.number} in {invoice.currency}"
        )
    if not payment.amount.amount > 0:
        raise PaymentError("a payment must be a positive amount")
    if invoice.issue_date and payment.received_on < invoice.issue_date:
        raise PaymentError("payment is dated before the invoice")
    balance = invoice.balance_due
    if not balance.amount > 0:
        raise PaymentError(f"{invoice.number} is already settled")
    applied = min(payment.amount, balance)
    invoice.payments.append(replace(payment, amount=applied))
    return payment.amount - applied


@dataclass(frozen=True)
class Allocation:
    """How much of a payment went to one invoice."""

    number: DocumentNumber
    amount: Money


def allocate_payment(
    invoices: Iterable[Invoice], payment: Payment
) -> tuple[list[Allocation], Money]:
    """Spread one payment over a customer's open invoices.

    Oldest due date first (then lowest number). Returns the allocations
    and whatever was left over.
    """
    open_invoices = sorted(
        (
            inv
            for inv in invoices
            if not inv.is_draft
            and inv.currency == payment.amount.currency
            and inv.balance_due.amount > 0
        ),
        key=lambda inv: (inv.due_date, inv.number),
    )
    left = payment.amount
    allocations = []
    for invoice in open_invoices:
        if not left.amount > 0:
            break
        unapplied = apply_payment(invoice, replace(payment, amount=left))
        applied = left - unapplied
        assert invoice.number is not None
        allocations.append(Allocation(invoice.number, applied))
        left = unapplied
    return allocations, left


@dataclass(frozen=True)
class Instalment:
    due: date
    amount: Money


def instalment_plan(
    invoice: Invoice, count: int, *, first_due: date, every_days: int = 30
) -> list[Instalment]:
    """Split the invoice's balance into ``count`` instalments.

    The instalments add up to the balance exactly; any odd minor units
    go on the earliest instalments.
    """
    if count < 1:
        raise ValueError("count must be at least 1")
    if every_days < 1:
        raise ValueError("every_days must be at least 1")
    shares = invoice.balance_due.allocate([1] * count)
    return [
        Instalment(first_due + timedelta(days=every_days * i), share)
        for i, share in enumerate(shares)
    ]
