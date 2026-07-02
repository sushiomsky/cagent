# Quality gates

Use the same local checks that CI runs before opening or merging a PR.

## Install development dependencies

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## Run all required checks

```bash
make check
```

This runs bytecode compilation, a conservative Ruff lint target and the test suite.

The required lint target is intentionally narrow so the project can gain a stable CI gate before a wider cleanup pass.

## Individual checks

```bash
make compile
make lint
make test
```

## Optional full lint

```bash
make lint-full
```

This runs the default Ruff ruleset and is intended for future cleanup PRs.

## Why this matters

The project is intentionally lightweight and dependency-minimal. The quality gate keeps that simplicity while catching check regressions before the agent workflow continues.
