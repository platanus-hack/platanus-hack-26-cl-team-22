"""Loader for data/seguridad/delitos_comuna_anio.csv (CEAD), split into the model's crime groups.

The DMCS total (teammate's aggregate, see data/seguridad/README.md) is split by what the
evidence on cameras and lighting supports: both meta-analyses find effects on property crime
and none on violent crime.
"""
from __future__ import annotations

import csv

import numpy as np

from core.seguridad import GROUPS
from experiments.datos_aire import ROOT

F_DELITOS = ROOT / "data" / "seguridad" / "delitos_comuna_anio.csv"
YEARS = tuple(range(2017, 2025))
COMPONENTS = {
    "property": ("robo_en_lugar_habitado", "robo_en_lugar_no_habitado", "robo_de_vehiculo",
                 "otros_robos_con_fuerza", "hurtos"),
    "violent": ("homicidios", "lesiones", "violaciones", "robo_con_violencia",
                "robo_por_sorpresa", "violencia_intrafamiliar"),
}


def load_rates(codes: tuple[str, ...]) -> np.ndarray:
    """(years, communes, groups) DMCS rates per 100,000 inhabitants (CEAD's own rate).

    Fails if property + violent does not add up to the DMCS total of the file.
    """
    index = {c: i for i, c in enumerate(codes)}
    group_of = {cat: g for g, cats in COMPONENTS.items() for cat in cats}
    rates = np.zeros((len(YEARS), len(codes), len(GROUPS)))
    total = np.zeros((len(YEARS), len(codes)))
    with F_DELITOS.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            y, c = YEARS.index(int(r["anio"])), index[r["codigo_comuna"]]
            if r["categoria"] == "dmcs_total":
                total[y, c] = float(r["tasa_100k"])
            elif r["categoria"] in group_of:
                rates[y, c, GROUPS.index(group_of[r["categoria"]])] += float(r["tasa_100k"])
    if not np.allclose(rates.sum(axis=2), total, rtol=1e-6):
        raise SystemExit("property + violent does not match dmcs_total in the CEAD file")
    return rates
