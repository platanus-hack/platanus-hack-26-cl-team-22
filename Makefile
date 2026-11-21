PY := .venv/bin/python

.PHONY: setup test lint clean

setup:            ## create .venv and install dev dependencies
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e ".[dev]"

test:             ## run the test suite
	$(PY) -m pytest

lint:             ## static checks
	$(PY) -m ruff check .

clean:
	rm -rf .pytest_cache .ruff_cache
