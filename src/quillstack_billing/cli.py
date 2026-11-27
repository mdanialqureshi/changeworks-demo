"""The ``quill`` command line.

Every command reads and writes one book file: ``--book PATH``, else the
``QUILL_BOOK`` environment variable, else ``quill-book.json`` in the
current directory. See ``docs/cli.md`` for the full reference.

Exit codes: 0 on success, 1 when Quillstack refuses the request (the
message says why), 2 for a usage error from argument parsing.
"""

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from . import __version__
from .aging import aging_report, format_report
from .credit_notes import issue_credit_note
from .customers import Customer
from .discounts import Coupon, DiscountKind
from .errors import BillingError
from .export import FORMATS, export
from .invoice import Invoice, InvoiceStatus, LineItem
from .money import Money, to_decimal
from .payments import apply_payment
from .records import Payment, PaymentMethod
from .regions import REGIONS, TaxCategory, local_date
from .storage import Book, load, save
from .terms import PaymentTerms

DEFAULT_BOOK = "quill-book.json"

Handler = Callable[[argparse.Namespace, Book], int]


# -- argument types ---------------------------------------------------------


def _date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"not a date (YYYY-MM-DD): {text!r}"
        ) from None


def _instant(text: str) -> datetime:
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        value = None
    if value is None or value.tzinfo is None:
        raise argparse.ArgumentTypeError(
            f"not a date-time with a UTC offset: {text!r}"
        )
    return value


def _amount(text: str) -> Decimal:
    try:
        value = to_decimal(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an amount: {text!r}") from None
    if value <= 0:
        raise argparse.ArgumentTypeError("amount must be positive")
    return value


def _terms(text: str) -> PaymentTerms:
    try:
        return PaymentTerms.parse(text)
    except BillingError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _line(text: str) -> tuple[str, Decimal, Decimal, str, Decimal]:
    """``DESCRIPTION|QTY|UNIT_PRICE[|CATEGORY[|DISCOUNT%]]``."""
    parts = [p.strip() for p in text.split("|")]
    if not 3 <= len(parts) <= 5:
        raise argparse.ArgumentTypeError(
            f"a line is DESCRIPTION|QTY|UNIT_PRICE[|CATEGORY[|DISCOUNT%]]: "
            f"{text!r}"
        )
    parts += ["standard", "0"][len(parts) - 3 :]
    description, qty, price, category, discount = parts
    try:
        TaxCategory(category)
        return (
            description,
            to_decimal(qty),
            to_decimal(price),
            category,
            to_decimal(discount.rstrip("%")),
        )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"bad line {text!r}: {exc}") from None


# -- commands ---------------------------------------------------------------


def _out(text: str = "") -> None:
    print(text)


def cmd_customer_add(args: argparse.Namespace, book: Book) -> int:
    try:
        customer = Customer(
            id=args.id or book.customers.next_id(),
            name=args.name,
            email=args.email,
            region=args.region,
            currency=args.currency or "",
            terms=str(args.terms),
            tax_exempt=args.tax_exempt,
            roll_weekends=args.roll_weekends,
            tags=tuple(args.tag),
        )
    except ValueError as exc:
        raise BillingError(str(exc)) from None
    book.customers.add(customer)
    _out(customer.id)
    return 0


def cmd_customer_list(args: argparse.Namespace, book: Book) -> int:
    for c in book.customers:
        flags = " tax-exempt" if c.tax_exempt else ""
        _out(f"{c.id}  {c.name:<28} {c.region} {c.currency} {c.terms}{flags}")
    return 0


def cmd_coupon_add(args: argparse.Namespace, book: Book) -> int:
    if args.percent is not None:
        kind, value, cur = DiscountKind.PERCENT, args.percent, None
    else:
        if not args.currency:
            raise BillingError("--amount needs --currency")
        kind, value, cur = DiscountKind.AMOUNT, args.amount, args.currency
    try:
        coupon = Coupon(
            code=args.code,
            kind=kind,
            value=value,
            currency=cur,
            valid_from=args.valid_from,
            valid_until=args.valid_until,
            min_subtotal=args.min_subtotal,
            max_redemptions=args.max_redemptions,
            stackable=not args.no_stack,
            priority=args.priority,
        )
    except ValueError as exc:
        raise BillingError(str(exc)) from None
    book.coupons.add(coupon)
    _out(coupon.code)
    return 0


def _issue_date(args: argparse.Namespace, customer: Customer) -> date:
    if args.date is not None:
        return args.date
    instant = args.at or datetime.now(UTC)
    return local_date(REGIONS[customer.region], instant)


def cmd_invoice_create(args: argparse.Namespace, book: Book) -> int:
    customer = book.customers.get(args.customer)
    invoice = Invoice(customer=customer, terms=args.terms, memo=args.memo)
    for description, qty, price, category, discount in args.line:
        try:
            line = LineItem(
                description=description,
                quantity=qty,
                unit_price=Money.of(price, customer.currency),
                category=TaxCategory(category),
                discount_percent=discount,
            )
        except ValueError as exc:
            raise BillingError(f"bad line {description!r}: {exc}") from None
        invoice.add_line(line)
    for code in args.coupon:
        invoice.add_coupon(book.coupons.get(code))
    if args.draft:
        book.invoices.append(invoice)
        _out("draft")
        return 0
    number = invoice.issue(book.numberer, _issue_date(args, customer))
    for coupon in invoice.coupons:
        book.coupons.redeem(coupon.code)
    book.invoices.append(invoice)
    _out(str(number))
    return 0


def render_invoice(invoice: Invoice, as_of: date | None = None) -> str:
    """The text ``quill invoice show`` prints."""
    totals = invoice.totals()
    tax_region = invoice.tax_region
    c = invoice.customer
    basis = "include" if tax_region.prices_include_tax else "exclude"
    rows = [
        f"Invoice {invoice.number or '(draft)'}  [{invoice.status}]",
        f"Customer: {c.id} {c.name} <{c.email}>",
        f"Region:   {tax_region.code} {tax_region.name} (prices {basis} tax)",
    ]
    if invoice.issue_date is not None:
        rows.append(
            f"Issued:   {invoice.issue_date}  Due: {invoice.due_date}  "
            f"Terms: {invoice.payment_terms}"
        )
    rows.append("")
    rows.append(
        f"  {'Description':<28}{'Qty':>8}{'Unit price':>14}{'Amount':>14}  Tax"
    )
    for line in invoice.lines:
        disc = f" (-{line.discount_percent}%)" if line.discount_percent else ""
        rows.append(
            f"  {line.description[:28]:<28}{line.quantity:>8}"
            f"{line.unit_price.plain():>14}{line.amount.plain():>14}"
            f"  {line.category}{disc}"
        )
    rows.append("")

    def money_row(label: str, value: Money) -> str:
        return f"{label:<30}{str(value):>22}"

    rows.append(money_row("Subtotal", totals.subtotal))
    for applied in totals.discounts:
        rows.append(money_row(f"Coupon {applied.code}", -applied.amount))
    for rate in totals.taxes.by_rate:
        label = f"Tax {rate.rate.normalize():f}% on {rate.net.plain()}"
        if tax_region.prices_include_tax:
            label += " (included)"
        rows.append(money_row(label, rate.tax))
    rows.append(money_row("Total", totals.total))
    rows.append(money_row("Paid", invoice.amount_paid))
    if invoice.credit_notes:
        rows.append(money_row("Credited", invoice.amount_credited))
    rows.append(money_row("Balance due", invoice.balance_due))
    if as_of is not None and invoice.days_overdue(as_of):
        rows.append(f"Overdue by {invoice.days_overdue(as_of)} days")
    if invoice.memo:
        rows += ["", f"Memo: {invoice.memo}"]
    return "\n".join(rows)


def cmd_invoice_show(args: argparse.Namespace, book: Book) -> int:
    _out(render_invoice(book.invoice(args.number), args.as_of))
    return 0


def cmd_invoice_export(args: argparse.Namespace, book: Book) -> int:
    invoices = [
        i
        for i in book.invoices
        if args.status is None or i.status == args.status
    ]
    text = export(invoices, args.format, as_of=args.as_of)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        _out(f"wrote {len(invoices)} invoices to {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_invoice_pay(args: argparse.Namespace, book: Book) -> int:
    invoice = book.invoice(args.number)
    payment = Payment(
        amount=Money.of(args.amount, invoice.currency),
        received_on=args.date or date.today(),
        method=PaymentMethod(args.method),
        reference=args.reference,
    )
    excess = apply_payment(invoice, payment)
    _out(f"{invoice.number}: balance {invoice.balance_due}")
    if not excess.is_zero:
        _out(f"unapplied: {excess} (held as customer credit)")
    return 0


def cmd_invoice_credit(args: argparse.Namespace, book: Book) -> int:
    invoice = book.invoice(args.number)
    note = issue_credit_note(
        invoice,
        Money.of(args.amount, invoice.currency),
        numberer=book.numberer,
        on=args.date or date.today(),
        reason=args.reason,
    )
    _out(f"{note.number} credits {note.amount} on {invoice.number}")
    return 0


def cmd_report_aging(args: argparse.Namespace, book: Book) -> int:
    as_of = args.as_of or date.today()
    report = aging_report(book.invoices, as_of, args.currency)
    _out(format_report(report))
    return 0


# -- parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quill", description="Quillstack invoicing."
    )
    parser.add_argument(
        "--version", action="version", version=f"quill {__version__}"
    )
    parser.add_argument(
        "--book",
        type=Path,
        default=None,
        help=f"book file (default: $QUILL_BOOK or {DEFAULT_BOOK})",
    )
    groups = parser.add_subparsers(dest="group", required=True)

    # customer
    customer = groups.add_parser("customer", help="manage customers")
    csub = customer.add_subparsers(dest="action", required=True)
    add = csub.add_parser("add", help="add a customer")
    add.add_argument("--id", help="C-NNNN (default: next free id)")
    add.add_argument("--name", required=True)
    add.add_argument("--email", required=True)
    add.add_argument(
        "--region", required=True, type=str.upper, choices=sorted(REGIONS)
    )
    add.add_argument("--currency", help="default: the region's currency")
    add.add_argument("--terms", type=_terms, default=_terms("net-30"))
    add.add_argument("--tax-exempt", action="store_true")
    add.add_argument("--roll-weekends", action="store_true")
    add.add_argument("--tag", action="append", default=[])
    add.set_defaults(handler=cmd_customer_add, writes=True)
    lst = csub.add_parser("list", help="list customers")
    lst.set_defaults(handler=cmd_customer_list, writes=False)

    # coupon
    coupon = groups.add_parser("coupon", help="manage coupons")
    ksub = coupon.add_subparsers(dest="action", required=True)
    kadd = ksub.add_parser("add", help="add a coupon")
    kadd.add_argument("code")
    value = kadd.add_mutually_exclusive_group(required=True)
    value.add_argument("--percent", type=_amount)
    value.add_argument("--amount", type=_amount)
    kadd.add_argument("--currency")
    kadd.add_argument("--valid-from", type=_date)
    kadd.add_argument("--valid-until", type=_date)
    kadd.add_argument("--min-subtotal", type=_amount)
    kadd.add_argument("--max-redemptions", type=int)
    kadd.add_argument("--priority", type=int, default=100)
    kadd.add_argument("--no-stack", action="store_true")
    kadd.set_defaults(handler=cmd_coupon_add, writes=True)

    # invoice
    invoice = groups.add_parser("invoice", help="create and settle invoices")
    isub = invoice.add_subparsers(dest="action", required=True)

    create = isub.add_parser("create", help="create and issue an invoice")
    create.add_argument("--customer", required=True)
    create.add_argument(
        "--line",
        type=_line,
        action="append",
        required=True,
        metavar="DESC|QTY|PRICE[|CATEGORY[|DISCOUNT%]]",
    )
    create.add_argument("--coupon", action="append", default=[])
    when = create.add_mutually_exclusive_group()
    when.add_argument("--date", type=_date, help="issue date")
    when.add_argument(
        "--at",
        type=_instant,
        help="issue instant with UTC offset; dated in the region's zone",
    )
    create.add_argument("--terms", type=_terms)
    create.add_argument("--memo", default="")
    create.add_argument("--draft", action="store_true")
    create.set_defaults(handler=cmd_invoice_create, writes=True)

    show = isub.add_parser("show", help="print an invoice")
    show.add_argument("number")
    show.add_argument("--as-of", type=_date)
    show.set_defaults(handler=cmd_invoice_show, writes=False)

    exp = isub.add_parser("export", help="export invoices")
    exp.add_argument("--format", choices=sorted(FORMATS), default="csv")
    exp.add_argument("--out")
    exp.add_argument("--as-of", type=_date)
    exp.add_argument("--status", choices=[str(s) for s in InvoiceStatus])
    exp.set_defaults(handler=cmd_invoice_export, writes=False)

    pay = isub.add_parser("pay", help="record a payment")
    pay.add_argument("number")
    pay.add_argument("--amount", type=_amount, required=True)
    pay.add_argument("--date", type=_date)
    pay.add_argument(
        "--method",
        choices=[str(m) for m in PaymentMethod],
        default=str(PaymentMethod.BANK_TRANSFER),
    )
    pay.add_argument("--reference", default="")
    pay.set_defaults(handler=cmd_invoice_pay, writes=True)

    credit = isub.add_parser("credit", help="issue a credit note")
    credit.add_argument("number")
    credit.add_argument("--amount", type=_amount, required=True)
    credit.add_argument("--date", type=_date)
    credit.add_argument("--reason", default="")
    credit.set_defaults(handler=cmd_invoice_credit, writes=True)

    # report
    report = groups.add_parser("report", help="reports")
    rsub = report.add_subparsers(dest="action", required=True)
    aging = rsub.add_parser("aging", help="accounts-receivable aging")
    aging.add_argument("--as-of", type=_date)
    aging.add_argument("--currency", type=str.upper)
    aging.set_defaults(handler=cmd_report_aging, writes=False)
    return parser


def book_path(args: argparse.Namespace) -> Path:
    if args.book is not None:
        return args.book
    return Path(os.environ.get("QUILL_BOOK") or DEFAULT_BOOK)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = book_path(args)
    try:
        book = load(path)
        status = args.handler(args, book)
        if args.writes:
            save(book, path)
    except BillingError as exc:
        print(f"quill: error: {exc}", file=sys.stderr)
        return 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
