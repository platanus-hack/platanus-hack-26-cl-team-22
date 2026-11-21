PY := .venv/bin/python

.PHONY: setup test lint experiments web web-build clean

setup:            ## create .venv and install dev dependencies
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e ".[dev]"

test:             ## run the whole validation suite
	$(PY) -m pytest

lint:             ## static checks
	$(PY) -m ruff check .

experiments:      ## replicas for the reference model -> results/*.csv
	$(PY) -m experiments.replicate

web:              ## run the landing page dev server (http://localhost:5173)
	cd web && npm install && npm run dev

web-build:        ## build the landing page into web/dist
	cd web && npm ci && npm run build

clean:
	rm -rf .pytest_cache .ruff_cache results/*.csv
