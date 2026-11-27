# quillstack-billing

Invoicing for Quillstack: money, customers, tax regions, coupons,
payment terms, numbering, payments, credit notes, dunning and aging,
with a small `quill` command line on top.

Quillstack and its tax regions (Aldermere, Brightwater, Corvane,
Duskfell, Emberlyn) are fictional; it is a real, tested library all
the same. This copy is the public demo repository for
[Changeworks](https://github.com/mdanialqureshi/changeworks), a small
software factory: its GitHub App opens branches and draft pull requests
here, and `changeworks cloud-check` runs a scripted item through it.

## Install

```sh
uv sync
uv run quill --help
```

Python 3.14 or newer. The only runtime dependency is `python-dateutil`.

## Quickstart

```python
from datetime import date
from decimal import Decimal

from quillstack_billing import Customer, Invoice, LineItem, Money, Numberer

acme = Customer("C-0001", "Acme Tools Ltd", "billing@acme.example", "ALD")
invoice = Invoice(acme)
invoice.add_line(
    LineItem("Widget", qty=Decimal(3), price=Money.of("10.00", "GBP"))
)
number = invoice.issue(Numberer(), date(2026, 3, 2))
print(number, invoice.total)
```

prints

```text
QS-2026-00001 GBP 36.00
```

From the command line:

```sh
uv run quill customer add --name "Acme Tools Ltd" \
    --email billing@acme.example --region ALD
uv run quill invoice create --customer C-0001 \
    --line "Widget|3|10.00" --date 2026-03-02
uv run quill invoice show QS-2026-00001
```

## Documentation

- [Docs index](docs/index.md)
- [Command line](docs/cli.md)
- [Tax regions](docs/tax-regions.md)
- [Rounding](docs/rounding.md)
- [Coupons and discounts](docs/discounts.md)
- [Dunning](docs/dunning.md)
- [Export formats](docs/export.md)
- [Contributing](CONTRIBUTING.md)

## Development

```sh
scripts/check.sh   # ruff (lint + format) and the test suite, offline
```

## Licence

MIT; see [LICENSE](LICENSE).
