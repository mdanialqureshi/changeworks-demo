from datetime import date

import pytest

from quillstack_billing.numbering import (
    DocumentKind,
    DocumentNumber,
    Numberer,
)

INVOICE = DocumentKind.INVOICE


def test_invoice_numbers_count_up() -> None:
    numberer = Numberer()
    first = numberer.next(INVOICE, date(2026, 1, 5))
    second = numberer.next(INVOICE, date(2026, 1, 6))
    assert (first.year, first.seq) == (2026, 1)
    assert (second.year, second.seq) == (2026, 2)


def test_sequence_restarts_each_year() -> None:
    numberer = Numberer()
    numberer.next(INVOICE, date(2026, 12, 30))
    numberer.next(INVOICE, date(2026, 12, 31))
    new_year = numberer.next(INVOICE, date(2027, 1, 1))
    assert (new_year.year, new_year.seq) == (2027, 1)


def test_state_round_trips() -> None:
    numberer = Numberer()
    numberer.next(INVOICE, date(2026, 2, 1))
    restored = Numberer(numberer.state())
    assert restored.next(INVOICE, date(2026, 2, 2)).seq == 2


def test_formatting() -> None:
    assert str(DocumentNumber(INVOICE, 2026, 42)) == "QS-2026-00042"
    credit = DocumentNumber(DocumentKind.CREDIT_NOTE, 2026, 3)
    assert str(credit) == "CN-2026-00003"
    assert credit.prefix == "CN"


def test_parse_round_trips() -> None:
    for text in ("QS-2026-00042", "CN-2031-99999"):
        assert str(DocumentNumber.parse(text)) == text


def test_construction_limits() -> None:
    with pytest.raises(ValueError):
        DocumentNumber(INVOICE, 2026, 100_000)
    with pytest.raises(ValueError):
        DocumentNumber(INVOICE, 1999, 1)


def test_sequence_overflow() -> None:
    numberer = Numberer()
    numberer.next(INVOICE, date(2026, 6, 1))
    (key,) = numberer.state()
    numberer = Numberer({key: 99_999})
    with pytest.raises(OverflowError):
        numberer.next(INVOICE, date(2026, 6, 1))
