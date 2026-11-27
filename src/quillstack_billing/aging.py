"""Accounts-receivable aging.

Every issued invoice with money owed is placed in a bucket by how many
days past its due date it is on the report date:

=========  ======================
bucket     days past due
=========  ======================
current    0 (not yet due)
1-30       1 to 30
31-60      31 to 60
61-90      61 to 90
90+        91 or more
=========  ======================

Amounts are kept per currency; they are never added across currencies.
"""

from dataclasses import dataclass, field

from .money import Money

BUCKETS = ("current", "1-30", "31-60", "61-90", "90+")


def bucket_for(days_overdue):
    """The bucket label for an invoice ``days_overdue`` days past due."""
    if days_overdue < 0:
        raise ValueError("days_overdue must not be negative")
    if days_overdue == 0:
        return "current"
    if days_overdue < 30:
        return "1-30"
    if days_overdue < 60:
        return "31-60"
    if days_overdue < 90:
        return "61-90"
    return "90+"


@dataclass
class AgingRow:
    """One customer's balances in one currency, by bucket."""

    customer_id: str
    customer_name: str
    currency: str
    buckets: dict = field(default_factory=dict)

    @property
    def total(self):
        return sum(self.buckets.values(), Money.zero(self.currency))


@dataclass
class AgingReport:
    as_of: object
    rows: list = field(default_factory=list)

    def totals(self):
        """Bucket totals per currency code."""
        result = {}
        for row in self.rows:
            per = result.setdefault(
                row.currency, {b: Money.zero(row.currency) for b in BUCKETS}
            )
            for bucket, amount in row.buckets.items():
                per[bucket] = per[bucket] + amount
        return result


def _row_key(invoice):
    return (invoice.customer.id, invoice.currency.code)


def aging_report(invoices, as_of, currency=None):
    """Age every open invoice on ``as_of``; optionally one currency."""
    rows = {}
    for invoice in invoices:
        if invoice.is_draft or not invoice.balance_due.amount > 0:
            continue
        if currency and invoice.currency.code != currency.upper():
            continue
        if invoice.issue_date and invoice.issue_date > as_of:
            continue
        key = _row_key(invoice)
        row = rows.get(key)
        if row is None:
            row = AgingRow(
                invoice.customer.id,
                invoice.customer.name,
                invoice.currency.code,
                {b: Money.zero(invoice.currency) for b in BUCKETS},
            )
            rows[key] = row
        bucket = bucket_for(invoice.days_overdue(as_of))
        row.buckets[bucket] = row.buckets[bucket] + invoice.balance_due
    ordered = sorted(rows.values(), key=lambda r: (r.currency, r.customer_id))
    return AgingReport(as_of, ordered)


def format_report(report):
    """The report as a fixed-width text table, one block per currency."""
    lines = [f"Aging as of {report.as_of.isoformat()}"]
    width = 14
    for code, totals in report.totals().items():
        lines.append("")
        header = f"{'customer':<10}" + "".join(
            f"{b:>{width}}" for b in BUCKETS
        )
        lines.append(f"{code}")
        lines.append(header + f"{'total':>{width}}")
        for row in (r for r in report.rows if r.currency == code):
            cells = "".join(
                f"{row.buckets[b].plain():>{width}}" for b in BUCKETS
            )
            lines.append(
                f"{row.customer_id:<10}{cells}{row.total.plain():>{width}}"
            )
        grand = sum(totals.values(), Money.zero(code))
        cells = "".join(f"{totals[b].plain():>{width}}" for b in BUCKETS)
        lines.append(f"{'TOTAL':<10}{cells}{grand.plain():>{width}}")
    if not report.rows:
        lines.append("No open invoices.")
    return "\n".join(lines)
