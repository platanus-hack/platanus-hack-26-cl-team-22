PY := .venv/bin/python

.PHONY: setup test lint demo web clean

setup:            ## create .venv and install dev dependencies
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e ".[dev]"

test:             ## run the test suite
	$(PY) -m pytest

lint:             ## static checks
	$(PY) -m ruff check .

demo:             ## print the three scenarios for a sample traveler
	$(PY) -m travel_sim simulate --city scl --days 5 --data-gb 20 --device esim-only --no-local-id

web:              ## local web UI at http://127.0.0.1:8000 (loopback only)
	$(PY) -m travel_sim.web

clean:
	rm -rf .pytest_cache .ruff_cache
