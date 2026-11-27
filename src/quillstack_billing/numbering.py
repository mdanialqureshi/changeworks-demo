"""Invoice and credit note numbers.

Numbers look like ``QS-2026-00042`` (invoices) and ``CN-2026-00003``
(credit notes): a prefix, the year of issue, and a five-digit sequence.
Each kind of document has its own gap-free sequence, which starts again
at 1 every calendar year; auditors check that no number is skipped.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Self


class DocumentKind(StrEnum):
    INVOICE = "invoice"
    CREDIT_NOTE = "credit-note"


PREFIXES: dict[DocumentKind, str] = {
    DocumentKind.INVOICE: "QS",
    DocumentKind.CREDIT_NOTE: "CN",
}
_KINDS = {prefix: kind for kind, prefix in PREFIXES.items()}
_NUMBER = re.compile(r"(?P<prefix>[A-Z]{2})-(?P<year>\d{4})-(?P<seq>\d{5})")
MAX_SEQUENCE = 99_999


@dataclass(frozen=True, order=True)
class DocumentNumber:
    """A parsed document number. Numbers sort by kind, year, sequence."""

    kind: DocumentKind
    year: int
    seq: int

    def __post_init__(self) -> None:
        if not 1 <= self.seq <= MAX_SEQUENCE:
            raise ValueError(f"sequence out of range: {self.seq}")
        if not 2000 <= self.year <= 9999:
            raise ValueError(f"year out of range: {self.year}")

    @classmethod
    def parse(cls, text: str) -> Self:
        """``DocumentNumber.parse("QS-2026-00042")``.

        The text must match exactly: upper-case prefix, four-digit year,
        five-digit sequence, nothing before or after.
        """
        match = _NUMBER.fullmatch(text)
        if match is None or match["prefix"] not in _KINDS:
            raise ValueError(f"not a document number: {text!r}")
        return cls(
            _KINDS[match["prefix"]], int(match["year"]), int(match["seq"])
        )

    @property
    def prefix(self) -> str:
        return PREFIXES[self.kind]

    def __str__(self) -> str:
        return f"{self.prefix}-{self.year}-{self.seq:05d}"


class Numberer:
    """Hands out the next number for each kind of document.

    ``state()`` and the ``counters`` argument let a book file save and
    restore the sequences.
    """

    def __init__(self, counters: Mapping[str, int] | None = None) -> None:
        self._counters: dict[str, int] = dict(counters or {})

    def next(self, kind: DocumentKind, on: date) -> DocumentNumber:
        """Take the next number for ``kind`` in ``on``'s year."""
        key = str(on.year)
        seq = self._counters.get(key, 0) + 1
        if seq > MAX_SEQUENCE:
            raise OverflowError(f"{kind} numbers for {on.year} are used up")
        self._counters[key] = seq
        return DocumentNumber(DocumentKind(kind), on.year, seq)

    def state(self) -> dict[str, int]:
        """The counters, for saving."""
        return dict(self._counters)
