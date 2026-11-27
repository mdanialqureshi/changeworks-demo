import pytest

from quillstack_billing.customers import (
    Customer,
    CustomerDirectory,
    DuplicateCustomerError,
)
from quillstack_billing.errors import (
    InvalidTermsError,
    NotFoundError,
    UnknownRegionError,
)
from quillstack_billing.terms import PaymentTerms, TermsKind


def make(cid: str = "C-0001", **kw: object) -> Customer:
    fields: dict[str, object] = {
        "name": "Acme Tools Ltd",
        "email": "billing@acme.example",
        "region": "ALD",
    }
    fields.update(kw)
    return Customer(cid, **fields)  # type: ignore[arg-type]


def test_defaults_come_from_the_region() -> None:
    customer = make(region="dsf")
    assert customer.region == "DSF"
    assert customer.currency == "JPY"
    assert customer.payment_terms == PaymentTerms(TermsKind.NET, 30)


def test_currency_can_be_overridden() -> None:
    assert make(currency="eur").currency == "EUR"


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("cid", "c-1", ValueError),
        ("cid", "C-00001", ValueError),
        ("name", "   ", ValueError),
        ("email", "not-an-email", ValueError),
        ("email", "a@b", ValueError),
        ("region", "XX", UnknownRegionError),
        ("terms", "net", InvalidTermsError),
    ],
)
def test_validation(field: str, value: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        if field == "cid":
            make(value)
        else:
            make(**{field: value})


def test_tags_are_sorted_and_unique() -> None:
    assert make(tags=("vip", "eu", "vip")).tags == ("eu", "vip")


def test_directory_add_get_and_duplicates() -> None:
    directory = CustomerDirectory([make()])
    assert directory.get("C-0001").name == "Acme Tools Ltd"
    assert "C-0001" in directory
    assert len(directory) == 1
    with pytest.raises(DuplicateCustomerError):
        directory.add(make())
    with pytest.raises(NotFoundError):
        directory.get("C-0404")


def test_replace_requires_an_existing_customer() -> None:
    directory = CustomerDirectory([make()])
    directory.replace(make(name="Acme Holdings"))
    assert directory.get("C-0001").name == "Acme Holdings"
    with pytest.raises(NotFoundError):
        directory.replace(make("C-0002"))


def test_find_by_text_and_tags() -> None:
    directory = CustomerDirectory(
        [
            make("C-0001", tags=("vip",)),
            make("C-0002", name="Bruecke", email="ap@bruecke.example"),
        ]
    )
    assert [c.id for c in directory.find("ACME")] == ["C-0001"]
    assert [c.id for c in directory.find("bruecke.example")] == ["C-0002"]
    assert [c.id for c in directory.find(tags=["vip"])] == ["C-0001"]
    assert len(directory.find()) == 2


def test_in_region_and_next_id() -> None:
    directory = CustomerDirectory(
        [make("C-0001"), make("C-0007", region="CRV")]
    )
    assert [c.id for c in directory.in_region("crv")] == ["C-0007"]
    assert directory.next_id() == "C-0008"
    assert CustomerDirectory().next_id() == "C-0001"
