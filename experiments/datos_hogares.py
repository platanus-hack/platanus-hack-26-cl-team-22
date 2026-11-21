"""Loaders for the census tables in data/censo/, aligned to the commune order of comunas_rm.csv."""
from __future__ import annotations

import csv

import numpy as np

from experiments.datos_aire import ROOT

CENSO = ROOT / "data" / "censo"
PERIODS = {"2012-2017": "mudanzas_2012_2017.csv", "2019-2024": "mudanzas_2019_2024.csv"}


def _read(name: str) -> list[dict[str, str]]:
    with (CENSO / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_moves(codes: tuple[str, ...], period: str) -> np.ndarray:
    """(origin, destination) persons; origin = commune 5 years before the census."""
    index = {c: i for i, c in enumerate(codes)}
    matrix = np.zeros((len(codes), len(codes)))
    for r in _read(PERIODS[period]):
        matrix[index[r["codigo_origen"]], index[r["codigo_destino"]]] += float(r["personas"])
    return matrix


def load_population_dwellings(codes: tuple[str, ...], year: int) -> tuple[np.ndarray, np.ndarray]:
    """Population (usual residents) and census dwellings per commune for 2017 or 2024."""
    rows = {r["codigo"]: r for r in _read("poblacion_viviendas.csv") if int(r["anio"]) == year}
    population = np.array([float(rows[c]["poblacion"]) for c in codes])
    dwellings = np.array([float(rows[c]["viviendas"]) for c in codes])
    return population, dwellings
