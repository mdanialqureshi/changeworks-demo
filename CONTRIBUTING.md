# Contributing

1. `uv sync` (Python 3.14+).
2. Make the change, with tests in `tests/` for any behaviour change.
3. Run `scripts/check.sh`: ruff lint, ruff format check and the whole
   test suite. It must pass before review.
4. Keep lines at 79 characters or fewer, amounts as `Decimal` (never
   `float`), and rounding explicit (see [rounding](docs/rounding.md)).
5. Update the docs in `docs/` when behaviour a user can see changes;
   `>>>` examples in the docs are run by the tests.

Issues use the forms in the repository's issue templates (bug, test,
docs, lint/types, dependency fix, small feature). Changes to CI,
agent configuration, `factory.toml` or the lockfile need a code
owner's review.
