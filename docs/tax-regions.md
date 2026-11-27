# Tax regions

Quillstack invoices customers in these (fictional) regions. The source
of truth is `REGIONS` in `src/quillstack_billing/regions.py`; this
table must match it.

| Code | Region | Currency | Standard | Reduced | Prices | Rounding | Level | Time zone |
|---|---|---|---|---|---|---|---|---|
| ALD | Aldermere | GBP | 20% | 5% | exclude tax | half-up | line | Europe/London |
| BRW | Brightwater | USD | 8.25% | 4.5% | exclude tax | half-up | line | America/New_York |
| CRV | Corvane | EUR | 19% | 9% | exclude tax | half-up | invoice | Europe/Berlin |
| EMB | Emberlyn | KWD | 5% | 2.5% | exclude tax | half-even | line | Asia/Kuwait |

The `zero` and `exempt` categories are 0% everywhere.

- **Prices**: whether line prices already include tax. When they do,
  the tax is worked out of the price and the invoice total is the sum
  of the lines.
- **Rounding** and **Level**: see [rounding](rounding.md).
- **Time zone**: decides the issue date when an invoice is created
  from an instant (`quill invoice create --at`).

```python
>>> from quillstack_billing.regions import region
>>> region("ald").rate("standard")
Decimal('20')
>>> region("ALD").rate("exempt")
Decimal('0')

```
