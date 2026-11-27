import json
from datetime import date

import pytest

from quillstack_billing.export import FIELDS, export, to_csv, to_json
from quillstack_billing.invoice import Invoice
from quillstack_billing.money import Money
from quillstack_billing.payments import apply_payment
from quillstack_billing.records import Payment


def test_json_export(issued_acme_invoice: Invoice) -> None:
    apply_payment(
        issued_acme_invoice,
        Payment(Money.of("10", "GBP"), date(2026, 3, 9)),
    )
    [item] = json.loads(to_json([issued_acme_invoice]))
    assert list(item)[: len(FIELDS)] == FIELDS
    assert item["number"] == "QS-2026-00001"
    assert item["customer_id"] == "C-0001"
    assert item["issue_date"] == "2026-03-02"
    assert item["due_date"] == "2026-04-01"
    assert item["currency"] == "GBP"
    assert (item["subtotal"], item["tax"], item["total"]) == (
        "39.98",
        "6.50",
        "46.48",
    )
    assert (item["paid"], item["balance"]) == ("10.00", "36.48")
    assert item["status"] == "partially-paid"
    assert item["days_overdue"] == ""
    assert [ln["description"] for ln in item["lines"]] == [
        "Widget",
        "Field guide",
    ]
    assert item["lines"][1]["category"] == "reduced"
    assert item["lines"][1]["amount"] == "9.98"


def test_json_without_lines_and_with_as_of(
    issued_acme_invoice: Invoice,
) -> None:
    text = to_json(
        [issued_acme_invoice], include_lines=False, as_of=date(2026, 4, 11)
    )
    [item] = json.loads(text)
    assert "lines" not in item
    assert item["days_overdue"] == "10"


def test_json_of_nothing() -> None:
    assert json.loads(to_json([])) == []


def test_csv_header(issued_acme_invoice: Invoice) -> None:
    rows = to_csv([issued_acme_invoice]).splitlines()
    assert rows[0] == ",".join(FIELDS)
    assert len(rows) == 2


def test_export_dispatch(issued_acme_invoice: Invoice) -> None:
    assert export([issued_acme_invoice], "csv").startswith("number,")
    assert export([issued_acme_invoice], "json").startswith("[")
    with pytest.raises(ValueError, match="xml"):
        export([issued_acme_invoice], "xml")
