import json
from pathlib import Path

import pytest
from conftest import Runner

from quillstack_billing import __version__

WIDGETS = ("--line", "Widget|3|10.00", "--line", "Field guide|2|4.99|reduced")


def create(quill: Runner, *extra: str) -> tuple[int, str, str]:
    return quill("invoice", "create", "--customer", "C-0001", *WIDGETS, *extra)


def test_version(quill: Runner) -> None:
    code, out, _ = quill("--version")
    assert (code, out) == (0, f"quill {__version__}\n")


def test_customer_add_and_list(quill_with_customer: Runner) -> None:
    code, out, _ = quill_with_customer("customer", "list")
    assert code == 0
    assert out.startswith("C-0001  Acme Tools Ltd")
    assert "ALD GBP net-30" in out


def test_customer_add_validation(quill: Runner) -> None:
    code, _, err = quill(
        "customer", "add", "--name", "X", "--email", "bad", "--region", "ALD"
    )
    assert code == 1
    assert err == "quill: error: not an email address: 'bad'\n"


def test_create_and_show(quill_with_customer: Runner) -> None:
    code, out, _ = create(quill_with_customer, "--date", "2026-03-02")
    assert (code, out) == (0, "QS-2026-00001\n")
    code, out, _ = quill_with_customer("invoice", "show", "qs-2026-00001")
    assert code == 0
    assert out.splitlines()[0] == "Invoice QS-2026-00001  [issued]"
    assert "Issued:   2026-03-02  Due: 2026-04-01  Terms: net-30" in out
    assert "Tax 20% on 30.00" in out
    assert "Tax 5% on 9.98" in out
    total = next(ln for ln in out.splitlines() if ln.startswith("Total"))
    assert total.endswith("GBP 46.48")


def test_create_at_dates_in_the_customer_zone(quill: Runner) -> None:
    quill(
        "customer",
        "add",
        "--name",
        "Kumo",
        "--email",
        "k@kumo.example",
        "--region",
        "DSF",
    )
    code, out, _ = quill(
        "invoice",
        "create",
        "--customer",
        "C-0001",
        "--line",
        "Pen|1|150",
        "--at",
        "2026-03-31T23:30:00+00:00",
    )
    assert code == 0
    code, out, _ = quill("invoice", "show", out.strip())
    assert "Issued:   2026-04-01" in out


def test_create_without_a_date_uses_today(quill_with_customer: Runner) -> None:
    code, out, _ = create(quill_with_customer)
    assert code == 0
    assert out.startswith("QS-")


def test_draft_is_not_numbered(quill_with_customer: Runner) -> None:
    code, out, _ = create(quill_with_customer, "--draft")
    assert (code, out) == (0, "draft\n")


def test_coupons(quill_with_customer: Runner, book_file: Path) -> None:
    code, out, _ = quill_with_customer(
        "coupon", "add", "ten", "--percent", "10", "--max-redemptions", "1"
    )
    assert (code, out) == (0, "TEN\n")
    code, _, _ = create(
        quill_with_customer, "--date", "2026-03-02", "--coupon", "TEN"
    )
    assert code == 0
    data = json.loads(book_file.read_text())
    assert data["redemptions"] == {"TEN": 1}
    code, out, _ = quill_with_customer("invoice", "show", "QS-2026-00001")
    assert "Coupon TEN" in out
    code, _, err = create(
        quill_with_customer, "--date", "2026-03-03", "--coupon", "TEN"
    )
    assert code == 1
    assert "used up" in err


def test_amount_coupon_needs_currency(quill: Runner) -> None:
    code, _, err = quill("coupon", "add", "FIVE", "--amount", "5")
    assert code == 1
    assert "--currency" in err


def test_pay_and_credit(quill_with_customer: Runner) -> None:
    create(quill_with_customer, "--date", "2026-03-02")
    code, out, _ = quill_with_customer(
        "invoice",
        "pay",
        "QS-2026-00001",
        "--amount",
        "40",
        "--date",
        "2026-03-09",
        "--method",
        "card",
    )
    assert (code, out) == (0, "QS-2026-00001: balance GBP 6.48\n")
    code, out, _ = quill_with_customer(
        "invoice", "credit", "QS-2026-00001", "--amount", "1.48"
    )
    assert code == 0
    assert out.endswith("credits GBP 1.48 on QS-2026-00001\n")
    code, out, _ = quill_with_customer(
        "invoice", "pay", "QS-2026-00001", "--amount", "10"
    )
    assert out.splitlines() == [
        "QS-2026-00001: balance GBP 0.00",
        "unapplied: GBP 5.00 (held as customer credit)",
    ]


def test_export_json_to_stdout(quill_with_customer: Runner) -> None:
    create(quill_with_customer, "--date", "2026-03-02")
    code, out, _ = quill_with_customer("invoice", "export", "--format", "json")
    assert code == 0
    [item] = json.loads(out)
    assert item["total"] == "46.48"


def test_export_csv_to_file(
    quill_with_customer: Runner, tmp_path: Path
) -> None:
    create(quill_with_customer, "--date", "2026-03-02")
    create(quill_with_customer, "--draft")
    target = tmp_path / "out.csv"
    code, out, _ = quill_with_customer(
        "invoice", "export", "--out", str(target), "--status", "issued"
    )
    assert (code, out) == (0, f"wrote 1 invoices to {target}\n")
    assert target.read_text().splitlines()[1].startswith("QS-2026-00001,")


def test_report_aging(quill_with_customer: Runner) -> None:
    create(quill_with_customer, "--date", "2026-01-01")
    code, out, _ = quill_with_customer(
        "report", "aging", "--as-of", "2026-03-17"
    )
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == "Aging as of 2026-03-17"
    assert lines[-1].startswith("TOTAL")
    assert "46.48" in lines[-1]


def test_unknown_invoice_is_an_error(quill_with_customer: Runner) -> None:
    code, out, err = quill_with_customer("invoice", "show", "QS-2026-00009")
    assert (code, out) == (1, "")
    assert err == "quill: error: no invoice QS-2026-00009\n"


def test_unknown_customer_is_an_error(quill: Runner) -> None:
    code, _, err = create(quill, "--date", "2026-03-02")
    assert code == 1
    assert err == "quill: error: no customer C-0001\n"


@pytest.mark.parametrize(
    "line_spec", ["Widget", "Widget|x|1", "Widget|1|1|luxury"]
)
def test_bad_line_is_a_usage_error(
    quill_with_customer: Runner, line_spec: str
) -> None:
    code, _, err = quill_with_customer(
        "invoice", "create", "--customer", "C-0001", "--line", line_spec
    )
    assert code == 2
    assert "argument --line" in err


def test_unknown_payment_method_is_a_usage_error(quill: Runner) -> None:
    code, out, err = quill(
        "invoice", "pay", "QS-2026-00001", "--amount", "5", "--method", "crad"
    )
    assert (code, out) == (2, "")
    assert err.splitlines()[-1] == (
        "quill invoice pay: error: argument --method: invalid choice: "
        "'crad' (choose from 'bank-transfer', 'card', 'cash', 'cheque')"
    )


def test_book_from_environment(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from quillstack_billing.cli import main

    path = tmp_path / "env-book.json"
    monkeypatch.setenv("QUILL_BOOK", str(path))
    assert main(["customer", "list"]) == 0
    assert (
        main(
            [
                "customer",
                "add",
                "--name",
                "Acme",
                "--email",
                "a@acme.example",
                "--region",
                "ald",
            ]
        )
        == 0
    )
    assert path.exists()
    capsys.readouterr()
