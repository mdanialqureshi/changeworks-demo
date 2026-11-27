"""Invoices, their lines and their totals.

An invoice starts as a draft, is issued once (which gives it a number
and an issue date), and is then settled by payments and credit notes.
Its status is always worked out from those facts, never stored.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from .customers import Customer
from .discounts import AppliedDiscount, Coupon, apply_coupons
from .errors import InvoiceStateError
from .money import Currency, Money, currency, sum_money, to_decimal
from .numbering import DocumentKind, DocumentNumber, Numberer
from .records import CreditNote, Payment
from .regions import TaxCategory, TaxRegion, region
from .taxes import TaxableLine, TaxSummary, compute_taxes
from .terms import PaymentTerms

HUNDRED = Decimal(100)


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially-paid"
    PAID = "paid"


@dataclass(frozen=True)
class LineItem:
    """One line of an invoice.

    ``discount_percent`` is a line discount (for example a volume
    discount), applied before any coupon.
    """

    description: str
    quantity: Decimal
    unit_price: Money
    category: TaxCategory = TaxCategory.STANDARD
    discount_percent: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity", to_decimal(self.quantity))
        object.__setattr__(
            self, "discount_percent", to_decimal(self.discount_percent)
        )
        object.__setattr__(self, "category", TaxCategory(self.category))
        if not self.description.strip():
            raise ValueError("a line needs a description")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.unit_price.is_negative:
            raise ValueError("unit price must not be negative")
        if not 0 <= self.discount_percent <= HUNDRED:
            raise ValueError("discount_percent must be between 0 and 100")

    @property
    def amount(self) -> Money:
        """Quantity times price, less the line discount, rounded."""
        gross = self.unit_price * self.quantity
        keep = (HUNDRED - self.discount_percent) / HUNDRED
        return (gross * keep).rounded()


@dataclass(frozen=True)
class InvoiceTotals:
    """Everything printed in an invoice's totals box."""

    subtotal: Money
    discounts: tuple[AppliedDiscount, ...]
    taxes: TaxSummary
    total: Money

    @property
    def discount(self) -> Money:
        return sum_money(
            (d.amount for d in self.discounts), self.total.currency
        )

    @property
    def tax(self) -> Money:
        return self.taxes.tax

    @property
    def net(self) -> Money:
        return self.total - self.tax


def spread(amount: Money, weights: Sequence[Money]) -> list[Money]:
    """Share ``amount`` across lines in proportion to ``weights``.

    Each share is rounded half-up; the last line takes whatever is left
    so the shares add up to ``amount`` exactly.
    """
    total = sum_money(weights, amount.currency)
    if not weights:
        return []
    if total.is_zero:
        return [Money.zero(amount.currency) for _ in weights]
    shares = [
        (amount * (w.amount / total.amount)).rounded() for w in weights[:-1]
    ]
    shares.append(amount - sum_money(shares, amount.currency))
    return shares


@dataclass
class Invoice:
    """An invoice to one customer."""

    customer: Customer
    lines: list[LineItem] = field(default_factory=list)
    terms: PaymentTerms | None = None
    coupons: list[Coupon] = field(default_factory=list)
    issue_date: date | None = None
    number: DocumentNumber | None = None
    payments: list[Payment] = field(default_factory=list)
    credit_notes: list[CreditNote] = field(default_factory=list)
    reminder_level: int | None = None
    memo: str = ""

    # -- facts ------------------------------------------------------------

    @property
    def currency(self) -> Currency:
        return currency(self.customer.currency)

    @property
    def tax_region(self) -> TaxRegion:
        return region(self.customer.region)

    @property
    def payment_terms(self) -> PaymentTerms:
        return self.terms or self.customer.payment_terms

    @property
    def is_draft(self) -> bool:
        return self.number is None

    @property
    def due_date(self) -> date | None:
        if self.issue_date is None:
            return None
        return self.payment_terms.due_date(
            self.issue_date, roll_weekends=self.customer.roll_weekends
        )

    # -- editing a draft --------------------------------------------------

    def _require_draft(self) -> None:
        if not self.is_draft:
            raise InvoiceStateError(f"{self.number} is already issued")

    def add_line(self, line: LineItem) -> None:
        self._require_draft()
        if line.unit_price.currency != self.currency:
            raise InvoiceStateError(
                f"line priced in {line.unit_price.currency}, "
                f"invoice in {self.currency}"
            )
        self.lines.append(line)

    def add_coupon(self, coupon: Coupon) -> None:
        self._require_draft()
        self.coupons.append(coupon)
        try:
            self.totals()
        except Exception:
            self.coupons.pop()
            raise

    def issue(self, numberer: Numberer, on: date) -> DocumentNumber:
        """Give the draft its number and issue date."""
        self._require_draft()
        if not self.lines:
            raise InvoiceStateError("cannot issue an invoice with no lines")
        self.issue_date = on
        self.totals()  # coupons must still be valid on the issue date
        self.number = numberer.next(DocumentKind.INVOICE, on)
        return self.number

    # -- money ------------------------------------------------------------

    def totals(self) -> InvoiceTotals:
        cur = self.currency
        amounts = [line.amount for line in self.lines]
        subtotal = sum_money(amounts, cur)
        on = self.issue_date or date.today()
        discounts = apply_coupons(subtotal, self.coupons, on)
        discount = sum_money((d.amount for d in discounts), cur)
        shares = spread(discount, amounts)
        taxable = [
            TaxableLine(amount - share, line.category)
            for line, amount, share in zip(
                self.lines, amounts, shares, strict=True
            )
        ]
        taxes = compute_taxes(
            self.tax_region,
            taxable,
            code=cur,
            exempt=self.customer.tax_exempt,
        )
        after_discount = subtotal - discount
        if self.tax_region.prices_include_tax:
            total = after_discount
        else:
            total = after_discount + taxes.tax
        return InvoiceTotals(subtotal, tuple(discounts), taxes, total)

    @property
    def total(self) -> Money:
        return self.totals().total

    @property
    def amount_paid(self) -> Money:
        return sum_money((p.amount for p in self.payments), self.currency)

    @property
    def amount_credited(self) -> Money:
        return sum_money((c.amount for c in self.credit_notes), self.currency)

    @property
    def balance_due(self) -> Money:
        return self.total - self.amount_paid - self.amount_credited

    @property
    def status(self) -> InvoiceStatus:
        if self.is_draft:
            return InvoiceStatus.DRAFT
        if not self.balance_due.amount > 0:
            return InvoiceStatus.PAID
        if self.payments or self.credit_notes:
            return InvoiceStatus.PARTIALLY_PAID
        return InvoiceStatus.ISSUED

    def days_overdue(self, as_of: date) -> int:
        """Whole days past the due date with money still owed, else 0."""
        due = self.due_date
        if due is None or not self.balance_due.amount > 0:
            return 0
        return max(0, (as_of - due).days)
