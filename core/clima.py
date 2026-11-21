"""Climate risk per commune and year from ARClim climate-model runs.

ARClim series are inputs, not results. Each replica draws one climate-model run (a GCM, then
one of its runs), and the engine computes each indicator's change against that run's own
1991-2020 mean: modelled absolute levels are biased, changes within a run are not.

Every risk reports its components in physical units. There is no composite score, because
weighting the components would put invented numbers into the result.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import reduce
from pathlib import Path

import numpy as np
import pandas as pd

from core.credibilidad import _stream

DATA = Path(__file__).resolve().parents[1] / "data" / "arclim"
BASELINE = (1991, 2020)
WINDOW_BEFORE, WINDOW_AFTER = 10, 9  # 20-year window t-10..t+9, as ARClim's 2041-2060

# risk -> [(indicator, kind of change, unit of the change)]
RISKS: dict[str, list[tuple[str, str, str]]] = {
    "hidrico": [("pr_sum", "rel", "%"), ("drought_periods", "abs", "pp")],
    "inundacion": [("maximum_daily_precipitation", "rel", "%"), ("days_over_50mm", "abs", "días")],
    "calor": [("hot_days", "abs", "días"), ("degdays_above_25", "abs", "grados-día")],
}

Run = tuple[str, str]  # (gcm, corrida)


@dataclass(frozen=True)
class Series:
    """One indicator under one scenario: values[run, commune, year]."""
    runs: list[Run]
    communes: list[str]
    years: np.ndarray
    values: np.ndarray


def load_series(indicator: str, scenario: str, root: Path = DATA) -> Series:
    df = pd.read_csv(root / f"series_{indicator}_{scenario}.csv.gz", dtype={"codigo_comuna": str})
    year_cols = [c for c in df.columns if c.isdigit()]
    runs = sorted(set(zip(df["gcm"], df["corrida"])))
    communes = sorted(df["codigo_comuna"].unique())
    values = np.full((len(runs), len(communes), len(year_cols)), np.nan)
    run_index = {r: i for i, r in enumerate(runs)}
    commune_index = {c: i for i, c in enumerate(communes)}
    for row, data in zip(df.itertuples(index=False), df[year_cols].to_numpy(float)):
        values[run_index[(row.gcm, row.corrida)], commune_index[row.codigo_comuna]] = data
    return Series(runs, communes, np.array([int(c) for c in year_cols]), values)


def change(values: np.ndarray, years: np.ndarray, kind: str, out_years: Sequence[int]) -> np.ndarray:
    """Change of the 20-year window around each out year against the 1991-2020 mean.

    values[..., year]; returns values[..., len(out_years)]. kind "rel" gives percent, "abs"
    the difference in the indicator's own unit.
    """
    years = np.asarray(years)
    base = values[..., (years >= BASELINE[0]) & (years <= BASELINE[1])].mean(axis=-1)
    out = np.empty(values.shape[:-1] + (len(out_years),))
    for i, t in enumerate(out_years):
        lo, hi = t - WINDOW_BEFORE, t + WINDOW_AFTER
        if lo < years.min() or hi > years.max():
            raise ValueError(f"year {t} needs data for {lo}-{hi}")
        window = values[..., (years >= lo) & (years <= hi)].mean(axis=-1)
        out[..., i] = 100.0 * (window / base - 1.0) if kind == "rel" else window - base
    return out


def common_runs(series: Iterable[Series]) -> list[Run]:
    """Runs present in every indicator, so one draw gives a coherent climate world."""
    return sorted(reduce(set.intersection, (set(s.runs) for s in series)))


def draw_run(runs: Sequence[Run], *, seed: int, replica: int) -> Run:
    """A climate model uniformly, then one of its runs: models with more runs are not favoured."""
    rng = _stream(seed, replica, "clima-corrida")
    gcms = sorted({g for g, _ in runs})
    gcm = gcms[rng.integers(len(gcms))]
    own = sorted(r for r in runs if r[0] == gcm)
    return own[rng.integers(len(own))]


def simulate_climate(scenario: str, *, seed: int, replicas: int, years: Sequence[int],
                     root: Path = DATA) -> dict:
    """Per risk and component, p10/p50/p90 of the change across replicas, per commune and year."""
    series = {ind: load_series(ind, scenario, root)
              for components in RISKS.values() for ind, _, _ in components}
    available = common_runs(series.values())
    drawn = [draw_run(available, seed=seed, replica=r) for r in range(replicas)]
    risks: dict[str, dict] = {}
    for risk, components in RISKS.items():
        risks[risk] = {}
        for ind, kind, unit in components:
            s = series[ind]
            per_run = change(s.values, s.years, kind, years)  # (runs, communes, years)
            idx = [s.runs.index(r) for r in drawn]
            q = np.quantile(per_run[idx], [0.1, 0.5, 0.9], axis=0)  # (3, communes, years)
            risks[risk][ind] = {
                "unidad": unit,
                "por_comuna": {
                    c: {k: np.round(q[j, ci], 2).tolist() for j, k in enumerate(("p10", "p50", "p90"))}
                    for ci, c in enumerate(s.communes)
                },
            }
    return {
        "escenario": scenario,
        "anios": list(years),
        "corridas_disponibles": [f"{g}/{c}" for g, c in available],
        "corridas": [f"{g}/{c}" for g, c in drawn],
        "riesgos": risks,
    }
