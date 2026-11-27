"""quillstack_billing: invoicing for Quillstack.

The package is a library first; ``quill`` (:mod:`.cli`) is a thin
command line over it. Quillstack and its tax regions are fictional.
"""

__version__ = "0.9.0"

from .customers import Customer, CustomerDirectory
from .discounts import Coupon, CouponBook, DiscountKind
from .errors import BillingError, CurrencyMismatchError
from .invoice import Invoice, InvoiceStatus, LineItem
from .money import Currency, Money
from .numbering import DocumentNumber, Numberer
from .regions import REGIONS, TaxCategory, region
from .terms import PaymentTerms

__all__ = [
    "REGIONS",
    "BillingError",
    "Coupon",
    "CouponBook",
    "Currency",
    "CurrencyMismatchError",
    "Customer",
    "CustomerDirectory",
    "DiscountKind",
    "DocumentNumber",
    "Invoice",
    "InvoiceStatus",
    "LineItem",
    "Money",
    "Numberer",
    "PaymentTerms",
    "TaxCategory",
    "__version__",
    "region",
]
