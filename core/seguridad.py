"""Security mechanism: crime rate per commune with inertia, interventions and neighbor effects.

For each commune c and crime group g (property / violent components of the DMCS), the
baseline log rate follows an AR(1) towards the commune's long-run mean (inertia):

    x[t+1] = mu[c, g] + phi[g] * (x[t] - mu[c, g]) + sigma[g] * eps[t, c, g]

Interventions scale the baseline rate. A measure in commune c, with coverage k (share of the
commune's crime in the treated places) and progress p in [0, 1]:

    treated commune:   rate *= 1 - k * p * r[g]
    neighbor commune:  rate *= 1 - s * k * p * r[g]

- r[g] = 1 - 1 / OR[g]: reduction in the treated area derived from a meta-analytic odds ratio,
  drawn once per replica from its confidence interval (log-normal).
- s: neighbor share, drawn once per replica from an interval with an open sign (s < 0 is
  displacement, s > 0 diffusion of benefits).

Population does not enter (context rule): rates come from CEAD, not from simulated population.
Every random draw comes from a stream keyed by commune, group or measure id, so adding or
removing a policy never changes the other draws (common random numbers for attribution).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import special

from core.credibilidad import DEFAULT_RHO, Measure, _stream, draw_execution

GROUPS: tuple[str, ...] = ("property", "violent")


@dataclass(frozen=True)
class EffectSize:
    """Meta-analytic odds ratio (OR > 1 = less crime) with its confidence interval."""

    odds_ratio: float
    lower: float
    upper: float
    level: float  # confidence level of the interval, e.g. 0.95 or 0.90

    def __post_init__(self) -> None:
        if not 0 < self.lower <= self.odds_ratio <= self.upper:
            raise ValueError("need 0 < lower <= odds_ratio <= upper")
        if not 0 < self.level < 1:
            raise ValueError("level must lie in (0, 1)")

    def draw_reduction(self, rng: np.random.Generator) -> float:
        """Reduction in the treated area, 1 - 1/OR, with log(OR) normal from the interval."""
        z = special.ndtri(0.5 + self.level / 2)
        se = (np.log(self.upper) - np.log(self.lower)) / (2 * z)
        odds = np.exp(rng.normal(np.log(self.odds_ratio), se))
        return float(1.0 - 1.0 / odds)


@dataclass(frozen=True)
class SecurityIntervention:
    measure: Measure
    communes: np.ndarray  # boolean mask of treated communes
    coverage: float  # share of each treated commune's crime in the treated places
    effects: dict[str, EffectSize]  # one per crime group
    years_to_full: int

    def __post_init__(self) -> None:
        if self.communes.dtype != bool or self.communes.ndim != 1:
            raise ValueError("communes must be a 1-D boolean mask")
        if not 0 <= self.coverage <= 1:
            raise ValueError("coverage must lie in [0, 1]")
        if set(self.effects) != set(GROUPS):
            raise ValueError(f"effects must cover exactly {GROUPS}")
        if self.years_to_full < 1:
            raise ValueError("years_to_full must be at least 1")


@dataclass(frozen=True)
class CrimeModel:
    codes: tuple[str, ...]
    log_mean: np.ndarray  # (n, groups): long-run mean of the log rate
    phi: np.ndarray  # (groups,)
    sigma: np.ndarray  # (groups,)
    neighbors: np.ndarray  # (n, n) boolean, zero diagonal

    def __post_init__(self) -> None:
        n, g = len(self.codes), len(GROUPS)
        if self.log_mean.shape != (n, g) or self.phi.shape != (g,) or self.sigma.shape != (g,):
            raise ValueError("log_mean must be (n, groups); phi and sigma (groups,)")
        if np.any(np.abs(self.phi) >= 1) or np.any(self.sigma < 0):
            raise ValueError("need |phi| < 1 and sigma >= 0")
        if self.neighbors.shape != (n, n) or self.neighbors.dtype != bool:
            raise ValueError("neighbors must be an (n, n) boolean matrix")
        if np.any(np.diag(self.neighbors)):
            raise ValueError("a commune is not its own neighbor")

    def baseline(self, log_rate0: np.ndarray, *, n_years: int, seed: int,
                 replica: int) -> np.ndarray:
        """(n_years, n, groups) baseline rates, no intervention."""
        n = len(self.codes)
        eps = np.empty((n_years, n, len(GROUPS)))
        for c, code in enumerate(self.codes):
            for g, group in enumerate(GROUPS):
                eps[:, c, g] = _stream(seed, replica, "crime-noise", code, group).standard_normal(
                    n_years)
        x = np.asarray(log_rate0, dtype=float).copy()
        if x.shape != (n, len(GROUPS)):
            raise ValueError("log_rate0 must be (n, groups)")
        out = np.empty((n_years, n, len(GROUPS)))
        for t in range(n_years):
            x = self.log_mean + self.phi * (x - self.log_mean) + self.sigma * eps[t]
            out[t] = np.exp(x)
        return out


def simulate_security(
    model: CrimeModel,
    log_rate0: np.ndarray,
    interventions: Sequence[SecurityIntervention],
    theta: np.ndarray,
    *,
    n_years: int,
    seed: int,
    replica: int,
    spillover: tuple[float, float],
    rho: float = DEFAULT_RHO,
) -> np.ndarray:
    """(n_years, n, groups) crime rates for one replica of one scenario."""
    lo, hi = spillover
    if lo > hi:
        raise ValueError("spillover must be (low, high) with low <= high")
    rates = model.baseline(log_rate0, n_years=n_years, seed=seed, replica=replica)
    measures = [iv.measure for iv in interventions]
    executed = draw_execution(theta, measures, n_years=n_years, seed=seed, replica=replica,
                              rho=rho)
    share = lo + (hi - lo) * _stream(seed, replica, "spillover").random()
    near = model.neighbors.astype(float)
    for iv, row in zip(interventions, executed, strict=True):
        if iv.communes.shape != (len(model.codes),):
            raise ValueError(f"intervention {iv.measure.id}: mask has the wrong length")
        progress = np.minimum(np.cumsum(row) / iv.years_to_full, 1.0)  # (years,)
        treated = iv.communes.astype(float)
        exposed_neighbors = np.minimum(near @ treated, 1.0) * (1 - treated)
        for g, group in enumerate(GROUPS):
            reduction = iv.effects[group].draw_reduction(
                _stream(seed, replica, "effect", iv.measure.id, group))
            cut = iv.coverage * progress[:, None] * reduction  # (years, 1)
            rates[:, :, g] *= 1 - cut * treated[None, :]
            rates[:, :, g] *= 1 - share * cut * exposed_neighbors[None, :]
    return rates
