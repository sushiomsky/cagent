# Quality gates

Use the same local checks that CI runs before opening or merging a PR.

## Install development dependencies

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## Run all checks

```bash
make check
```

This runs:

```text
python -m compileall cagent tests
ruff check .
pytest -q
```

## Individual checks

```bash
make compile
make lint
make test
```

## Why this matters

The project is intentionally lightweight and dependency-minimal. The quality gate keeps that simplicity while catching syntax errors, lint issues and test regressions before the agent workflow continues.
