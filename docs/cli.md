# The `quill` command line

`quill` is a thin layer over the library. Every command reads and
writes one book file (JSON):

1. `--book PATH` if given (before the command: `quill --book b.json
   invoice show ...`);
2. otherwise the `QUILL_BOOK` environment variable;
3. otherwise `quill-book.json` in the current directory.

A missing book file is treated as an empty book; commands that change
anything write it back atomically.

## Exit codes and errors

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | Quillstack refused the request; stderr has one line, `quill: error: <reason>` |
| 2 | usage error from argument parsing; stderr has the usage line, then one `quill ...: error: <message>` line |

Scripts may rely on the wording of these error lines: it is the same on
every supported Python version.

## Customers

```sh
quill customer add --name NAME --email EMAIL --region CODE \
    [--id C-NNNN] [--currency CODE] [--terms TERMS] \
    [--tax-exempt] [--roll-weekends] [--tag TAG ...]
quill customer list
```

`--region` is one of the [tax regions](tax-regions.md). `--currency`
defaults to the region's currency and `--terms` to `net-30`. Prints
the new customer's id.

## Coupons

```sh
quill coupon add CODE (--percent N | --amount N --currency CODE) \
    [--valid-from DATE] [--valid-until DATE] [--min-subtotal N] \
    [--max-redemptions N] [--priority N] [--no-stack]
```

See [coupons and discounts](discounts.md) for how coupons combine.

## Invoices

### `quill invoice create`

```sh
quill invoice create --customer ID --line "DESC|QTY|PRICE[|CATEGORY[|DISCOUNT%]]" ... \
    [--coupon CODE ...] [--date DATE | --at DATETIME] [--terms TERMS] \
    [--memo TEXT] [--draft]
```

- `--line` may be repeated. `CATEGORY` is `standard` (default),
  `reduced`, `zero` or `exempt`; `DISCOUNT%` is a line discount.
- `--date` is the issue date. `--at` is an instant with a UTC offset
  (`2026-03-31T23:30:00+00:00`); the issue date is that instant's date
  in the customer's region. With neither, the current instant is used.
- `--terms` overrides the customer's payment terms for this invoice:
  `due-on-receipt`, `net-N` or `eom-N`.
- `--draft` saves the invoice unnumbered.

Prints the new invoice number, or `draft`.

### `quill invoice show NUMBER [--as-of DATE]`

Prints the invoice: customer, dates, lines, coupons, tax by rate,
total, payments, credits and balance. With `--as-of`, also how many
days it is overdue.

### `quill invoice export [--format csv|json] [--out FILE] [--as-of DATE] [--status STATUS]`

Writes every invoice (or those with `--status`: `draft`, `issued`,
`partially-paid`, `paid`) in the chosen format to stdout or `--out`.
`--as-of` fills the `days_overdue` column. The columns are listed in
[export formats](export.md).

### `quill invoice pay NUMBER --amount N [--date DATE] [--method METHOD] [--reference TEXT]`

Records a payment. `METHOD` is `bank-transfer` (default), `card`,
`cash` or `cheque`. Money beyond the balance is not applied; the
command reports it as customer credit.

### `quill invoice credit NUMBER --amount N [--date DATE] [--reason TEXT]`

Issues a credit note against an issued invoice and prints its number.
