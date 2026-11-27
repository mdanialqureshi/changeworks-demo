# Export formats

`quill invoice export` and `quillstack_billing.export` write invoices
as CSV or JSON.

## Columns

| Column | Meaning |
|---|---|
| `number` | invoice number, empty for drafts |
| `customer_id`, `customer_name` | the customer |
| `issue_date`, `due_date` | ISO dates, empty for drafts |
| `currency` | ISO 4217 code |
| `subtotal`, `discount`, `tax`, `total` | the totals box |
| `paid`, `credited`, `balance` | settlement so far |
| `status` | `draft`, `issued`, `partially-paid` or `paid` |
| `days_overdue` | filled only when an as-of date is given |

Amounts are plain decimal strings with exactly the currency's minor
units: `1234.50` for pounds, `1200` for yen, `2.500` for dinars. They
are never floats.

## CSV

A header row, then one row per invoice. Fields that contain commas or
quotes are quoted the usual CSV way. A subset of columns can be asked
for (library only), in any order.

## JSON

A pretty-printed array of objects with the columns above, in that
order, plus `lines`: each line's description, quantity, unit price,
category, discount and amount.
