"""The docs check: examples in the docs run, and links resolve.

* Every ``>>>`` example in ``docs/*.md`` and in the package's
  docstrings runs as a doctest.
* Every relative Markdown link in ``README.md`` and ``docs/*.md``
  points at a file that exists.
"""

import doctest
import importlib
import pkgutil
import re
from pathlib import Path

import pytest

import quillstack_billing

ROOT = Path(__file__).resolve().parent.parent
DOCS = sorted((ROOT / "docs").glob("*.md"))
LINK = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
MODULES = sorted(
    m.name
    for m in pkgutil.iter_modules(quillstack_billing.__path__)
    if m.name != "__main__"
)


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_doc_examples_run(path: Path) -> None:
    result = doctest.testfile(
        str(path),
        module_relative=False,
        optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE,
        verbose=False,
    )
    assert result.failed == 0


@pytest.mark.parametrize("name", MODULES)
def test_docstring_examples_run(name: str) -> None:
    module = importlib.import_module(f"quillstack_billing.{name}")
    result = doctest.testmod(module, verbose=False)
    assert result.failed == 0


@pytest.mark.parametrize(
    "path", [ROOT / "README.md", *DOCS], ids=lambda p: p.name
)
def test_relative_links_resolve(path: Path) -> None:
    for target in LINK.findall(path.read_text(encoding="utf-8")):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        file_part = target.split("#", 1)[0]
        assert (path.parent / file_part).exists(), f"{path.name}: {target}"


def test_every_doc_is_linked_from_the_index() -> None:
    index = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    for path in DOCS:
        if path.name != "index.md":
            assert f"({path.name})" in index, path.name
