.PHONY: check test lint lint-full compile

PYTHON ?= python
RUFF_CRITICAL ?= E9,F821,F822,F823

check: compile lint test

compile:
	$(PYTHON) -m compileall cagent tests

lint:
	ruff check --select $(RUFF_CRITICAL) .

lint-full:
	ruff check .

test:
	pytest -q
