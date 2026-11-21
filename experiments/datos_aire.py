"""Loaders for the clean air tables in data/. Joins use the official 5-digit commune code."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.estado import SOURCES

ROOT = Path(__file__).resolve().parent.parent
F_COMUNAS = ROOT / "data" / "comunas_rm.csv"
F_EMISIONES = ROOT / "data" / "emisiones" / "pm25_por_comuna_fuente.csv"
F_ESTACIONES = ROOT / "data" / "aire" / "estaciones.csv"
F_ANUAL = ROOT / "data" / "aire" / "pm25_anual.csv"

# RETC source label -> position in core.estado.SOURCES.
SOURCE_OF_RETC = {"lena": "heating", "transporte": "transport", "industria": "industry",
                  "otras": "other"}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _float(value: str | None) -> float | None:
    value = (value or "").strip().replace(",", ".")
    return float(value) if value else None


@dataclass(frozen=True)
class Communes:
    codes: tuple[str, ...]
    names: tuple[str, ...]
    lat: np.ndarray
    lon: np.ndarray
    population_2017: np.ndarray
    population_2024: np.ndarray


def load_communes() -> Communes:
    rows = _read(F_COMUNAS)
    return Communes(
        codes=tuple(r["codigo_comuna"] for r in rows),
        names=tuple(r["comuna"] for r in rows),
        lat=np.array([float(r["lat"]) for r in rows]),
        lon=np.array([float(r["lon"]) for r in rows]),
        population_2017=np.array([float(r["poblacion_2017"]) for r in rows]),
        population_2024=np.array([float(r["poblacion_2024"]) for r in rows]),
    )


def load_emissions(codes: tuple[str, ...], year: int) -> tuple[np.ndarray, dict[str, list[str]]]:
    """(n_communes, n_sources) t/year for `year`, and the communes missing per source.

    A commune absent from the RETC table for a source is left at 0 and reported as missing.
    """
    index = {c: i for i, c in enumerate(codes)}
    matrix = np.zeros((len(codes), len(SOURCES)))
    seen: dict[str, set[str]] = {s: set() for s in SOURCES}
    for r in _read(F_EMISIONES):
        if int(r["anio"]) != year or r["fuente"] not in SOURCE_OF_RETC:
            continue
        value = _float(r["toneladas_anio"])
        if value is None or r["codigo_comuna"] not in index:
            continue
        source = SOURCE_OF_RETC[r["fuente"]]
        matrix[index[r["codigo_comuna"]], SOURCES.index(source)] += value
        seen[source].add(r["codigo_comuna"])
    missing = {s: [c for c in codes if c not in seen[s]] for s in SOURCES}
    return matrix, missing


@dataclass(frozen=True)
class Stations:
    ids: tuple[str, ...]
    names: tuple[str, ...]
    lat: np.ndarray
    lon: np.ndarray
    pm25: np.ndarray


def load_stations(year: int, column: str = "pm25_media") -> Stations:
    """Stations with a valid annual mean in `year` (the table leaves it empty below 75 % days)."""
    meta = {r["estacion_id"]: r for r in _read(F_ESTACIONES)}
    ids, names, lat, lon, values = [], [], [], [], []
    for r in _read(F_ANUAL):
        value = _float(r.get(column))
        m = meta.get(r["estacion_id"])
        if int(r["anio"]) != year or value is None or m is None:
            continue
        ids.append(r["estacion_id"])
        names.append(r["estacion"])
        lat.append(float(m["lat"]))
        lon.append(float(m["lon"]))
        values.append(value)
    return Stations(tuple(ids), tuple(names), np.array(lat), np.array(lon), np.array(values))
