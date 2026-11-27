"""Payment terms and due dates.

Supported terms, written the way they appear on an invoice:

``due-on-receipt``
    due on the issue date.
``net-N``
    due N days after the issue date (``net-30`` issued 1 March is due
    31 March).
``eom-N``
    due N days after the end of the month the invoice was issued in
    (``eom-15`` issued 10 March is due 15 April). ``eom`` alone is
    ``eom-0``: due on the last day of the issue month.

A customer with ``roll_weekends`` set has a due date that lands on a
Saturday or Sunday moved to the following Monday.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Self

from dateutil.relativedelta import relativedelta

from .errors import InvalidTermsError

_TERMS = re.compile(
    r"^\s*(?:(?P<receipt>due[- ]on[- ]receipt)"
    r"|(?P<kind>net|eom)(?:[- ]?(?P<days>\d{1,3}))?)\s*$",
    re.IGNORECASE,
)


class TermsKind(StrEnum):
    DUE_ON_RECEIPT = "due-on-receipt"
    NET = "net"
    END_OF_MONTH = "eom"


@dataclass(frozen=True)
class PaymentTerms:
    """When an invoice falls due, relative to its issue date."""

    kind: TermsKind
    days: int = 0

    def __post_init__(self) -> None:
        if self.days < 0 or self.days > 365:
            raise InvalidTermsError("terms must be 0 to 365 days")
        if self.kind is TermsKind.DUE_ON_RECEIPT and self.days:
            raise InvalidTermsError("due-on-receipt takes no days")

    @classmethod
    def parse(cls, text: str) -> Self:
        """Terms from text such as ``net-30``, ``NET 30`` or ``eom``.

        ``net`` with no number is refused: it is a common typo for
        ``net-30`` and guessing would set the wrong due date.
        """
        match = _TERMS.match(text)
        if match is None:
            raise InvalidTermsError(f"unrecognised payment terms {text!r}")
        if match["receipt"]:
            return cls(TermsKind.DUE_ON_RECEIPT)
        kind = TermsKind(match["kind"].lower())
        if match["days"] is None and kind is TermsKind.NET:
            raise InvalidTermsError("net terms need a number of days")
        return cls(kind, int(match["days"] or 0))

    def due_date(self, issued: date, *, roll_weekends: bool = False) -> date:
        """The date an invoice issued on ``issued`` is due."""
        match self.kind:
            case TermsKind.DUE_ON_RECEIPT:
                due = issued
            case TermsKind.NET:
                due = issued + timedelta(days=self.days)
            case TermsKind.END_OF_MONTH:
                month_end = issued.replace(day=1) + relativedelta(months=1)
                due = month_end + timedelta(days=self.days)
        if roll_weekends:
            due = next_business_day(due)
        return due

    def __str__(self) -> str:
        if self.kind is TermsKind.DUE_ON_RECEIPT:
            return str(self.kind)
        if self.kind is TermsKind.END_OF_MONTH and not self.days:
            return "eom"
        return f"{self.kind}-{self.days}"


def next_business_day(day: date) -> date:
    """``day`` itself on a weekday; otherwise the following Monday."""
    while day.weekday() > 5:
        day += timedelta(days=1)
    return day


def end_of_month(day: date) -> date:
    """The last day of ``day``'s month.

    >>> end_of_month(date(2028, 2, 3))
    datetime.date(2028, 2, 29)
    """
    return day + relativedelta(day=31)
