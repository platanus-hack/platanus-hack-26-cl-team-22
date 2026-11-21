PY := .venv/bin/python

.PHONY: setup test lint experiments licitaciones simulate validate web web-build clean

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

licitaciones:     ## download and aggregate ChileCompra procurement data -> data/licitaciones/
	$(PY) -m datos.licitaciones.fetch_licitaciones --desde 2024-01 --hasta 2024-12

simulate:         ## calibrate air and households -> promises -> viz/datos/simulacion.json
	$(PY) -m experiments.calibrar_aire
	$(PY) -m experiments.calibrar_hogares
	$(PY) -m experiments.calibrar_seguridad
	$(PY) -m experiments.promesas
	$(PY) -m experiments.simular

validate:         ## out-of-sample test vs no change and trend -> docs/validacion.md, README table
	$(PY) -m experiments.calibrar_aire
	$(PY) -m experiments.calibrar_hogares
	$(PY) -m experiments.calibrar_seguridad
	$(PY) -m experiments.validar_poblacion
	$(PY) -m experiments.validar

web:              ## run the landing page dev server (http://localhost:5173)
	cd web && npm install && npm run dev

web-build:        ## build the landing page into web/dist
	cd web && npm ci && npm run build

clean:
	rm -rf .pytest_cache .ruff_cache results/*.csv
