"""Customers and the directory that holds them."""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from .errors import BillingError, NotFoundError
from .money import currency
from .regions import region
from .terms import PaymentTerms

CUSTOMER_ID = re.compile(r"^C-\d{4}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class DuplicateCustomerError(BillingError):
    """A customer with that id is already in the directory."""


@dataclass(frozen=True)
class Customer:
    """Someone Quillstack invoices.

    ``currency`` defaults to the region's currency. ``terms`` is the
    customer's default payment terms. ``roll_weekends`` moves due dates
    that fall on a weekend to the next Monday.
    """

    id: str
    name: str
    email: str
    region: str
    currency: str = ""
    terms: str = "net-30"
    tax_exempt: bool = False
    roll_weekends: bool = False
    tags: tuple[str, ...] = field(default=(), compare=False)

    def __post_init__(self) -> None:
        if not CUSTOMER_ID.match(self.id):
            raise ValueError(f"customer id must look like C-0001: {self.id}")
        if not self.name.strip():
            raise ValueError("customer name must not be empty")
        if not EMAIL.match(self.email):
            raise ValueError(f"not an email address: {self.email!r}")
        tax_region = region(self.region)
        object.__setattr__(self, "region", tax_region.code)
        code = self.currency or tax_region.currency
        object.__setattr__(self, "currency", currency(code).code)
        PaymentTerms.parse(self.terms)  # fail early on bad terms
        object.__setattr__(self, "tags", tuple(sorted(set(self.tags))))

    @property
    def payment_terms(self) -> PaymentTerms:
        return PaymentTerms.parse(self.terms)


class CustomerDirectory:
    """Customers by id, in the order they were added."""

    def __init__(self, customers: Iterable[Customer] = ()) -> None:
        self._by_id: dict[str, Customer] = {}
        for customer in customers:
            self.add(customer)

    def add(self, customer: Customer) -> None:
        if customer.id in self._by_id:
            raise DuplicateCustomerError(f"{customer.id} already exists")
        self._by_id[customer.id] = customer

    def replace(self, customer: Customer) -> None:
        """Update an existing customer's details."""
        self.get(customer.id)
        self._by_id[customer.id] = customer

    def get(self, customer_id: str) -> Customer:
        try:
            return self._by_id[customer_id]
        except KeyError:
            raise NotFoundError(f"no customer {customer_id}") from None

    def find(self, text: str = "", tags: list[str] = []) -> list[Customer]:
        """Customers whose name or email contains ``text`` (any case)
        and who carry every tag in ``tags``."""
        needle = text.casefold()
        wanted = set(tags)
        return [
            c
            for c in self._by_id.values()
            if (needle in c.name.casefold() or needle in c.email.casefold())
            and wanted <= set(c.tags)
        ]

    def in_region(self, code: str) -> list[Customer]:
        wanted = region(code).code
        return [c for c in self._by_id.values() if c.region == wanted]

    def next_id(self) -> str:
        """The next free id, one above the highest in use."""
        numbers = [int(c.id[2:]) for c in self._by_id.values()]
        return f"C-{max(numbers, default=0) + 1:04d}"

    def __iter__(self) -> Iterator[Customer]:
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, customer_id: object) -> bool:
        return customer_id in self._by_id
