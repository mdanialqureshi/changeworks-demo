#!/usr/bin/env sh
# The repository's one check command (named in CLAUDE.md and AGENTS.md).
# Lint, format check and the test suite. Offline after `uv sync --frozen`:
# it needs no network and no secrets, so it can run under
# `docker run --network none`.
set -eu
cd "$(dirname "$0")/.."
export UV_OFFLINE=1
uv run --frozen ruff check --no-cache .
uv run --frozen ruff format --check --no-cache .
uv run --frozen pytest -q -p no:cacheprovider
