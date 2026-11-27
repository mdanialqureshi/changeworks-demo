"""Shared fixtures: one customer per region, invoice builders, the CLI."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from quillstack_billing.cli import main
from quillstack_billing.customers import Customer
from quillstack_billing.invoice import Invoice, LineItem
from quillstack_billing.money import Money
from quillstack_billing.numbering import Numberer
from quillstack_billing.regions import TaxCategory


@pytest.fixture
def acme() -> Customer:
    """Aldermere (GBP, prices exclude tax, line-level half-up)."""
    return Customer("C-0001", "Acme Tools Ltd", "billing@acme.example", "ALD")


@pytest.fixture
def bruecke() -> Customer:
    """Corvane (EUR, invoice-level rounding)."""
    return Customer("C-0002", "Bruecke GmbH", "ap@bruecke.example", "CRV")


@pytest.fixture
def kumo() -> Customer:
    """Duskfell (JPY, prices include tax, fractions dropped)."""
    return Customer("C-0003", "Kumo Stationery", "kaikei@kumo.example", "DSF")


@pytest.fixture
def oasis() -> Customer:
    """Emberlyn (KWD, three places, half-even)."""
    return Customer("C-0004", "Oasis Trading", "fin@oasis.example", "EMB")


@pytest.fixture
def harbor() -> Customer:
    """Brightwater (USD)."""
    return Customer("C-0005", "Harbor Supply", "ar@harbor.example", "BRW")


@pytest.fixture
def numberer() -> Numberer:
    return Numberer()


def line(
    description: str,
    quantity: str,
    price: str,
    code: str,
    category: TaxCategory = TaxCategory.STANDARD,
    discount: str = "0",
) -> LineItem:
    return LineItem(
        description,
        Decimal(quantity),
        Money.of(price, code),
        category,
        Decimal(discount),
    )


@pytest.fixture
def acme_invoice(acme: Customer) -> Invoice:
    """Draft: 3 x 10.00 standard + 2 x 4.99 reduced (GBP 46.48)."""
    invoice = Invoice(customer=acme)
    invoice.add_line(line("Widget", "3", "10.00", "GBP"))
    invoice.add_line(
        line("Field guide", "2", "4.99", "GBP", TaxCategory.REDUCED)
    )
    return invoice


@pytest.fixture
def issued_acme_invoice(acme_invoice: Invoice, numberer: Numberer) -> Invoice:
    acme_invoice.issue(numberer, date(2026, 3, 2))
    return acme_invoice


Runner = Callable[..., tuple[int, str, str]]


@pytest.fixture
def book_file(tmp_path: Path) -> Path:
    return tmp_path / "book.json"


@pytest.fixture
def quill(book_file: Path, capsys: pytest.CaptureFixture[str]) -> Runner:
    """Run ``quill --book <tmp> ARGS``; return (exit code, out, err)."""

    def run(*argv: str) -> tuple[int, str, str]:
        try:
            code = main(["--book", str(book_file), *argv])
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
        out, err = capsys.readouterr()
        return code, out, err

    return run


@pytest.fixture
def quill_with_customer(quill: Runner) -> Runner:
    code, out, _ = quill(
        "customer",
        "add",
        "--name",
        "Acme Tools Ltd",
        "--email",
        "billing@acme.example",
        "--region",
        "ALD",
    )
    assert (code, out) == (0, "C-0001\n")
    return quill
