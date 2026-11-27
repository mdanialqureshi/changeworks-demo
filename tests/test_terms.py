from datetime import date

import pytest

from quillstack_billing.errors import InvalidTermsError
from quillstack_billing.terms import (
    PaymentTerms,
    TermsKind,
    end_of_month,
    next_business_day,
)


@pytest.mark.parametrize(
    ("text", "kind", "days"),
    [
        ("net-30", TermsKind.NET, 30),
        ("NET 14", TermsKind.NET, 14),
        ("net7", TermsKind.NET, 7),
        ("due-on-receipt", TermsKind.DUE_ON_RECEIPT, 0),
        ("Due on receipt", TermsKind.DUE_ON_RECEIPT, 0),
        ("eom", TermsKind.END_OF_MONTH, 0),
        ("EOM-15", TermsKind.END_OF_MONTH, 15),
    ],
)
def test_parse(text: str, kind: TermsKind, days: int) -> None:
    assert PaymentTerms.parse(text) == PaymentTerms(kind, days)


@pytest.mark.parametrize(
    "text", ["net", "net-", "net-1000", "30 days", "", "eom-x", "net--3"]
)
def test_parse_rejects(text: str) -> None:
    with pytest.raises(InvalidTermsError):
        PaymentTerms.parse(text)


def test_invalid_construction() -> None:
    with pytest.raises(InvalidTermsError):
        PaymentTerms(TermsKind.NET, 400)
    with pytest.raises(InvalidTermsError):
        PaymentTerms(TermsKind.DUE_ON_RECEIPT, 3)


@pytest.mark.parametrize("text", ["net-30", "due-on-receipt", "eom", "eom-15"])
def test_str_round_trips(text: str) -> None:
    assert str(PaymentTerms.parse(text)) == text


def test_net_due_date() -> None:
    terms = PaymentTerms.parse("net-30")
    assert terms.due_date(date(2026, 3, 1)) == date(2026, 3, 31)
    assert terms.due_date(date(2026, 12, 15)) == date(2027, 1, 14)


def test_due_on_receipt() -> None:
    terms = PaymentTerms.parse("due-on-receipt")
    assert terms.due_date(date(2026, 5, 9)) == date(2026, 5, 9)


def test_roll_weekends_moves_sunday_to_monday() -> None:
    terms = PaymentTerms.parse("net-14")
    issued = date(2026, 3, 1)  # due Sunday 15 March
    assert terms.due_date(issued) == date(2026, 3, 15)
    assert terms.due_date(issued, roll_weekends=True) == date(2026, 3, 16)


def test_roll_weekends_leaves_weekdays_alone() -> None:
    terms = PaymentTerms.parse("net-30")
    issued = date(2026, 3, 2)  # due Wednesday 1 April
    assert terms.due_date(issued, roll_weekends=True) == date(2026, 4, 1)


def test_next_business_day_on_a_weekday() -> None:
    assert next_business_day(date(2026, 3, 4)) == date(2026, 3, 4)


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 1, 10), date(2026, 1, 31)),
        (date(2028, 2, 3), date(2028, 2, 29)),
        (date(2026, 2, 28), date(2026, 2, 28)),
        (date(2026, 12, 1), date(2026, 12, 31)),
    ],
)
def test_end_of_month(day: date, expected: date) -> None:
    assert end_of_month(day) == expected
