"""Plain records attached to an invoice: payments and credit notes.

They carry no behaviour; :mod:`.payments` and :mod:`.credit_notes`
create them and check the rules.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from .money import Money
from .numbering import DocumentNumber


class PaymentMethod(StrEnum):
    BANK_TRANSFER = "bank-transfer"
    CARD = "card"
    CASH = "cash"
    CHEQUE = "cheque"


@dataclass(frozen=True)
class Payment:
    """Money received against one invoice."""

    amount: Money
    received_on: date
    method: PaymentMethod = PaymentMethod.BANK_TRANSFER
    reference: str = ""


@dataclass(frozen=True)
class CreditNote:
    """A reduction of an issued invoice's balance."""

    number: DocumentNumber
    invoice_number: DocumentNumber
    amount: Money
    issued_on: date
    reason: str = ""
