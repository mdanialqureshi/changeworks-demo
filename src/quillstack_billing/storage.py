"""The book: a JSON file holding everything the CLI knows.

A book has customers, coupons, invoices (with their payments and credit
notes) and the numbering counters. It is written atomically: to a
temporary file next to the book, then renamed over it.
"""

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from .customers import Customer, CustomerDirectory
from .discounts import Coupon, CouponBook, DiscountKind
from .errors import NotFoundError, StorageError
from .invoice import Invoice, LineItem
from .money import Money
from .numbering import DocumentNumber, Numberer
from .records import CreditNote, Payment, PaymentMethod
from .regions import TaxCategory
from .terms import PaymentTerms

FORMAT_VERSION = 1


def _day(text: Optional[str]) -> Optional[date]:
    return date.fromisoformat(text) if text else None


def _money(data: Dict[str, str]) -> Money:
    return Money.of(data["amount"], data["currency"])


def _money_dict(money: Money) -> Dict[str, str]:
    return {"amount": str(money.amount), "currency": money.currency.code}


def customer_to_dict(customer: Customer) -> Dict[str, Any]:
    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "region": customer.region,
        "currency": customer.currency,
        "terms": customer.terms,
        "tax_exempt": customer.tax_exempt,
        "roll_weekends": customer.roll_weekends,
        "tags": list(customer.tags),
    }


def customer_from_dict(data: Dict[str, Any]) -> Customer:
    return Customer(
        id=data["id"],
        name=data["name"],
        email=data["email"],
        region=data["region"],
        currency=data.get("currency", ""),
        terms=data.get("terms", "net-30"),
        tax_exempt=data.get("tax_exempt", False),
        roll_weekends=data.get("roll_weekends", False),
        tags=tuple(data.get("tags", ())),
    )


def coupon_to_dict(coupon: Coupon) -> Dict[str, Any]:
    return {
        "code": coupon.code,
        "kind": str(coupon.kind),
        "value": str(coupon.value),
        "currency": coupon.currency,
        "valid_from": coupon.valid_from and coupon.valid_from.isoformat(),
        "valid_until": coupon.valid_until and coupon.valid_until.isoformat(),
        "min_subtotal": (
            None if coupon.min_subtotal is None else str(coupon.min_subtotal)
        ),
        "max_redemptions": coupon.max_redemptions,
        "stackable": coupon.stackable,
        "priority": coupon.priority,
    }


def coupon_from_dict(data: Dict[str, Any]) -> Coupon:
    return Coupon(
        code=data["code"],
        kind=DiscountKind(data["kind"]),
        value=data["value"],
        currency=data.get("currency"),
        valid_from=_day(data.get("valid_from")),
        valid_until=_day(data.get("valid_until")),
        min_subtotal=data.get("min_subtotal"),
        max_redemptions=data.get("max_redemptions"),
        stackable=data.get("stackable", True),
        priority=data.get("priority", 100),
    )


def invoice_to_dict(invoice: Invoice) -> Dict[str, Any]:
    return {
        "number": str(invoice.number) if invoice.number else None,
        "customer": invoice.customer.id,
        "issue_date": invoice.issue_date and invoice.issue_date.isoformat(),
        "terms": str(invoice.terms) if invoice.terms else None,
        "coupons": [c.code for c in invoice.coupons],
        "memo": invoice.memo,
        "reminder_level": invoice.reminder_level,
        "lines": [
            {
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": _money_dict(line.unit_price),
                "category": str(line.category),
                "discount_percent": str(line.discount_percent),
            }
            for line in invoice.lines
        ],
        "payments": [
            {
                "amount": _money_dict(p.amount),
                "received_on": p.received_on.isoformat(),
                "method": str(p.method),
                "reference": p.reference,
            }
            for p in invoice.payments
        ],
        "credit_notes": [
            {
                "number": str(n.number),
                "amount": _money_dict(n.amount),
                "issued_on": n.issued_on.isoformat(),
                "reason": n.reason,
            }
            for n in invoice.credit_notes
        ],
    }


def invoice_from_dict(
    data: Dict[str, Any], customers: CustomerDirectory, coupons: CouponBook
) -> Invoice:
    number = data.get("number")
    invoice = Invoice(
        customer=customers.get(data["customer"]),
        terms=PaymentTerms.parse(data["terms"]) if data.get("terms") else None,
        coupons=[coupons.get(code) for code in data.get("coupons", [])],
        issue_date=_day(data.get("issue_date")),
        number=DocumentNumber.parse(number) if number else None,
        memo=data.get("memo", ""),
        reminder_level=data.get("reminder_level"),
    )
    invoice.lines = [
        LineItem(
            description=line["description"],
            quantity=line["quantity"],
            unit_price=_money(line["unit_price"]),
            category=TaxCategory(line.get("category", "standard")),
            discount_percent=line.get("discount_percent", "0"),
        )
        for line in data.get("lines", [])
    ]
    invoice.payments = [
        Payment(
            amount=_money(p["amount"]),
            received_on=date.fromisoformat(p["received_on"]),
            method=PaymentMethod(p.get("method", "bank-transfer")),
            reference=p.get("reference", ""),
        )
        for p in data.get("payments", [])
    ]
    if invoice.number is not None:
        invoice.credit_notes = [
            CreditNote(
                number=DocumentNumber.parse(n["number"]),
                invoice_number=invoice.number,
                amount=_money(n["amount"]),
                issued_on=date.fromisoformat(n["issued_on"]),
                reason=n.get("reason", ""),
            )
            for n in data.get("credit_notes", [])
        ]
    return invoice


@dataclass
class Book:
    """Everything in one book file."""

    customers: CustomerDirectory = field(default_factory=CustomerDirectory)
    coupons: CouponBook = field(default_factory=CouponBook)
    invoices: List[Invoice] = field(default_factory=list)
    numberer: Numberer = field(default_factory=Numberer)

    def invoice(self, number: str) -> Invoice:
        """The invoice numbered ``number``."""
        try:
            wanted = DocumentNumber.parse(number.strip().upper())
        except ValueError as exc:
            raise NotFoundError(str(exc)) from None
        for invoice in self.invoices:
            if invoice.number == wanted:
                return invoice
        raise NotFoundError(f"no invoice {wanted}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": FORMAT_VERSION,
            "customers": [customer_to_dict(c) for c in self.customers],
            "coupons": [coupon_to_dict(c) for c in self.coupons],
            "redemptions": self.coupons.state(),
            "invoices": [invoice_to_dict(i) for i in self.invoices],
            "counters": self.numberer.state(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Book":
        if data.get("version") != FORMAT_VERSION:
            raise StorageError(
                f"unsupported book version {data.get('version')!r}"
            )
        customers = CustomerDirectory(
            customer_from_dict(c) for c in data.get("customers", [])
        )
        coupons = CouponBook(
            (coupon_from_dict(c) for c in data.get("coupons", [])),
            redemptions=data.get("redemptions", {}),
        )
        invoices = [
            invoice_from_dict(i, customers, coupons)
            for i in data.get("invoices", [])
        ]
        return cls(customers, coupons, invoices, Numberer(data["counters"]))


def load(path: Path) -> Book:
    """Read a book; a missing file is an empty book."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Book()
    except OSError as exc:
        raise StorageError(f"cannot read {path}: {exc}") from exc
    try:
        return Book.from_dict(json.loads(text))
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise StorageError(f"{path} is not a valid book: {exc}") from exc


def save(book: Book, path: Path) -> None:
    """Write ``book`` to ``path`` atomically."""
    text = json.dumps(book.to_dict(), indent=2, ensure_ascii=False) + "\n"
    directory = path.parent if str(path.parent) else Path(".")
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
