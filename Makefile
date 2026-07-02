.PHONY: check test lint lint-full compile

PYTHON ?= python

check: compile lint test

compile:
	$(PYTHON) -m compileall cagent tests

lint:
	ruff check --select E9 .

lint-full:
	ruff check .

test:
	pytest -q
