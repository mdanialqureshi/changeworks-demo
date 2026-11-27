import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from quillstack_billing.credit_notes import issue_credit_note
from quillstack_billing.customers import Customer
from quillstack_billing.discounts import Coupon, DiscountKind
from quillstack_billing.errors import NotFoundError, StorageError
from quillstack_billing.invoice import Invoice
from quillstack_billing.money import Money
from quillstack_billing.payments import apply_payment
from quillstack_billing.records import Payment, PaymentMethod
from quillstack_billing.storage import Book, load, save
from quillstack_billing.terms import PaymentTerms


@pytest.fixture
def book(acme: Customer, acme_invoice: Invoice) -> Book:
    book = Book()
    book.customers.add(acme)
    coupon = Coupon(
        "TEN",
        DiscountKind.PERCENT,
        Decimal(10),
        valid_until=date(2026, 12, 31),
        min_subtotal=Decimal(20),
    )
    book.coupons.add(coupon)
    acme_invoice.terms = PaymentTerms.parse("net-14")
    acme_invoice.memo = "PO 7781"
    acme_invoice.add_coupon(coupon)
    acme_invoice.issue(book.numberer, date(2026, 3, 2))
    book.coupons.redeem("TEN")
    apply_payment(
        acme_invoice,
        Payment(
            Money.of("10", "GBP"), date(2026, 3, 9), PaymentMethod.CASH, "r1"
        ),
    )
    issue_credit_note(
        acme_invoice,
        Money.of("1.83", "GBP"),
        numberer=book.numberer,
        on=date(2026, 3, 10),
        reason="late",
    )
    book.invoices.append(acme_invoice)
    return book


def test_round_trip(book: Book, tmp_path: Path) -> None:
    path = tmp_path / "book.json"
    save(book, path)
    loaded = load(path)
    assert loaded.to_dict() == book.to_dict()
    invoice = loaded.invoice("QS-2026-00001")
    assert invoice.total == Money.of("41.83", "GBP")
    assert invoice.balance_due == Money.of("30.00", "GBP")
    assert invoice.payments[0].method is PaymentMethod.CASH
    assert invoice.credit_notes[0].reason == "late"
    assert loaded.coupons.redemptions("TEN") == 1
    assert str(invoice.payment_terms) == "net-14"
    assert invoice.memo == "PO 7781"


def test_amounts_are_stored_as_strings(book: Book, tmp_path: Path) -> None:
    path = tmp_path / "book.json"
    save(book, path)
    data = json.loads(path.read_text())
    line = data["invoices"][0]["lines"][0]
    assert line["unit_price"] == {"amount": "10.00", "currency": "GBP"}


def test_missing_file_is_an_empty_book(tmp_path: Path) -> None:
    book = load(tmp_path / "nope.json")
    assert len(book.customers) == 0
    assert book.invoices == []


@pytest.mark.parametrize(
    "text", ["not json", '{"version": 99}', '{"version": 1}', "[]"]
)
def test_bad_files(tmp_path: Path, text: str) -> None:
    path = tmp_path / "book.json"
    path.write_text(text)
    with pytest.raises(StorageError):
        load(path)


def test_save_leaves_no_temporary_files(book: Book, tmp_path: Path) -> None:
    save(book, tmp_path / "book.json")
    save(book, tmp_path / "book.json")
    assert [p.name for p in tmp_path.iterdir()] == ["book.json"]


def test_invoice_lookup(book: Book) -> None:
    assert book.invoice(" qs-2026-00001 ").memo == "PO 7781"
    with pytest.raises(NotFoundError):
        book.invoice("QS-2026-00002")
    with pytest.raises(NotFoundError):
        book.invoice("garbage")
