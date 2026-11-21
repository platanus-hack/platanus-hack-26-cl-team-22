PY := .venv/bin/python

.PHONY: setup test lint experiments simulate clean

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

simulate:         ## air model: calibrate -> promises comparison -> viz/datos/simulacion.json
	$(PY) -m experiments.calibrar_aire
	$(PY) -m experiments.promesas
	$(PY) -m experiments.simular

clean:
	rm -rf .pytest_cache .ruff_cache results/*.csv
