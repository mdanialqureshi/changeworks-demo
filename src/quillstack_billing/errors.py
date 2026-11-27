"""Exceptions raised by quillstack_billing.

Every error the library raises on purpose is a :class:`BillingError`, so
callers (and the CLI) can catch one type and show its message.
"""


class BillingError(Exception):
    """Base class for every deliberate quillstack_billing error."""


class CurrencyMismatchError(BillingError):
    """Two amounts in different currencies were combined or compared."""


class UnknownCurrencyError(BillingError):
    """A currency code is not in :data:`money.CURRENCIES`."""


class UnknownRegionError(BillingError):
    """A tax region code is not in :data:`regions.REGIONS`."""


class InvalidTermsError(BillingError):
    """Payment terms text could not be parsed."""


class CouponError(BillingError):
    """A coupon is unknown, expired, used up, or cannot be combined."""


class InvoiceStateError(BillingError):
    """The invoice is in the wrong state for the requested change."""


class PaymentError(BillingError):
    """A payment is invalid for the invoice it was applied to."""


class CreditNoteError(BillingError):
    """A credit note is invalid for the invoice it credits."""


class NotFoundError(BillingError):
    """A customer, coupon or invoice does not exist."""


class StorageError(BillingError):
    """A book file is missing, unreadable or malformed."""
