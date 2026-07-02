.PHONY: check test lint compile

PYTHON ?= python

check: compile lint test

compile:
	$(PYTHON) -m compileall cagent tests

lint:
	ruff check .

test:
	pytest -q
