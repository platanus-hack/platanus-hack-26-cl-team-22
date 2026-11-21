"""Annual cycle: measures executed each year change emissions, the air model turns them into PM2.5.

One simulated year (docs/contexto-proyecto.md, section 4), air-only version:
1. draw which measures are executed this year (core.credibilidad);
2. each executed year moves a measure one step towards its full effect on emissions;
3. the coupled air model gives PM2.5 per commune.

Households (core.hogares) enter through `heating_scale`: when residential heating follows
residents, people moving to a commune raise its heating emissions. Security is not modelled.

theta is an input so that history-based credibility, theta = 0 (no execution) and theta = 1
(the plan as written) all run through the same path.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from core.aire import AirModel
from core.credibilidad import DEFAULT_RHO, Measure, draw_execution
from core.estado import SOURCES, RegionState


@dataclass(frozen=True)
class Intervention:
    """A plan measure and the emissions it changes when executed.

    factor_at_full: emissions multiplier once fully executed (0 = ban, 0.7 = -30 %).
    years_to_full: executed years needed to reach the full effect; each executed year delivers
    an equal share. Years without execution deliver nothing.
    """

    measure: Measure
    source: str
    communes: np.ndarray
    factor_at_full: float
    years_to_full: int

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise ValueError(f"unknown source {self.source!r}; expected one of {SOURCES}")
        if self.communes.dtype != bool or self.communes.ndim != 1:
            raise ValueError("communes must be a 1-D boolean mask")
        if not 0 <= self.factor_at_full:
            raise ValueError("factor_at_full must be non-negative")
        if self.years_to_full < 1:
            raise ValueError("years_to_full must be at least 1")


def emission_multipliers(
    interventions: Sequence[Intervention], executed: np.ndarray, n_communes: int
) -> np.ndarray:
    """(n_years, n_communes, n_sources) multiplier applied to the initial emissions."""
    n_years = executed.shape[1]
    mult = np.ones((n_years, n_communes, len(SOURCES)))
    for iv, row in zip(interventions, executed, strict=True):
        if iv.communes.shape != (n_communes,):
            raise ValueError(f"intervention {iv.measure.id}: mask must have {n_communes} entries")
        progress = np.minimum(np.cumsum(row) / iv.years_to_full, 1.0)
        step = 1.0 - progress * (1.0 - iv.factor_at_full)
        mult[:, iv.communes, SOURCES.index(iv.source)] *= step[:, None]
    return mult


def simulate(
    initial: RegionState,
    air: AirModel,
    interventions: Sequence[Intervention],
    theta: np.ndarray,
    *,
    n_years: int,
    seed: int,
    replica: int,
    rho: float = DEFAULT_RHO,
    heating_scale: np.ndarray | None = None,
) -> np.ndarray:
    """PM2.5 trajectory (n_years, n_communes) for one replica of one scenario.

    heating_scale (n_years, n_communes), optional: multiplies residential heating emissions,
    e.g. population / initial population when heating follows residents (core.hogares). Policy
    multipliers apply on top, so a ban also covers the heating of people who moved in.
    """
    if air.n_communes != initial.n_communes:
        raise ValueError("air model and state must cover the same communes")
    if heating_scale is not None:
        heating_scale = np.asarray(heating_scale, dtype=float)
        if heating_scale.shape != (n_years, initial.n_communes) or np.any(heating_scale < 0):
            raise ValueError(f"heating_scale must be non-negative with shape "
                             f"({n_years}, {initial.n_communes})")
    measures = [iv.measure for iv in interventions]
    executed = draw_execution(theta, measures, n_years=n_years, seed=seed, replica=replica,
                              rho=rho)
    mult = emission_multipliers(interventions, executed, initial.n_communes)
    if heating_scale is not None:
        mult[:, :, SOURCES.index("heating")] *= heating_scale
    return np.array([air.concentration(initial.emissions * mult[t]) for t in range(n_years)])
