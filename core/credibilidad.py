"""Execution credibility: which plan measures are carried out each simulated year.

Design and sources: docs/credibilidad.md.

Two random levels, kept on separate streams:
- theta (credibility): drawn once per replica from Beta(alpha, beta), correlated within an
  executor (shared uncertainty about the executor). Epistemic uncertainty.
- execution: drawn once per year with theta fixed, correlated within an executor through a
  one-factor Gaussian copula. Aleatoric uncertainty.

Every measure and every executor owns a random stream keyed by its id, so adding or removing
a measure never changes the draws of the others (common random numbers for attribution).
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy import special, stats

Provenance = Literal["medida", "tasa_base", "supuesto"]

# Assumption (docs/credibilidad.md): within-executor failure correlation until history allows
# estimating it.
DEFAULT_RHO = 0.3
# Assumption (docs/credibilidad.md): share of the uncertainty about a measure's credibility that
# belongs to its executor. Chosen before running the promises comparison, which reports 0 too.
DEFAULT_RHO_THETA = 0.5


@dataclass(frozen=True)
class BetaCredibility:
    """Beta(alpha, beta) belief about a measure's annual probability of execution."""

    alpha: float
    beta: float

    def __post_init__(self) -> None:
        if not (self.alpha > 0 and self.beta > 0):
            raise ValueError("alpha and beta must be positive")

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    def update(self, fulfilled: int, total: int) -> BetaCredibility:
        """Beta-Binomial posterior after observing `fulfilled` of `total` commitments."""
        if total < 0 or not 0 <= fulfilled <= total:
            raise ValueError("need 0 <= fulfilled <= total")
        return BetaCredibility(self.alpha + fulfilled, self.beta + total - fulfilled)

    def summary(self) -> dict[str, float]:
        """p10 / media / p90, the shape published in simulacion.json."""
        p10, p90 = stats.beta.ppf([0.1, 0.9], self.alpha, self.beta)
        return {"p10": float(p10), "media": self.mean, "p90": float(p90)}


@dataclass(frozen=True)
class Measure:
    id: str
    executor: str
    credibility: BetaCredibility
    provenance: Provenance


def _stream(seed: int, replica: int, *labels: str) -> np.random.Generator:
    """Random stream keyed by labels, stable across runs and independent of list order."""
    digest = hashlib.sha256("\x1f".join(labels).encode()).digest()
    key = int.from_bytes(digest[:8], "little")
    return np.random.default_rng(np.random.SeedSequence([seed, replica, key]))


def draw_theta(
    measures: Sequence[Measure],
    *,
    seed: int,
    replica: int,
    rho_theta: float = DEFAULT_RHO_THETA,
) -> np.ndarray:
    """One credibility value per measure for this replica.

    Each theta keeps its own Beta marginal exactly; rho_theta makes the measures of one executor
    share part of the uncertainty about that executor (one-factor Gaussian copula):

        latent_i = sqrt(rho_theta) * z[executor] + sqrt(1 - rho_theta) * eps_i
        theta_i  = BetaPPF(Phi(latent_i); alpha_i, beta_i)
    """
    _check_unique(measures)
    if not 0 <= rho_theta < 1:
        raise ValueError("rho_theta must lie in [0, 1)")
    shocks: dict[str, float] = {}
    theta = np.empty(len(measures))
    for i, m in enumerate(measures):
        if m.executor not in shocks:
            shocks[m.executor] = float(
                _stream(seed, replica, "theta-shock", m.executor).standard_normal())
        own = float(_stream(seed, replica, "theta", m.id).standard_normal())
        latent = np.sqrt(rho_theta) * shocks[m.executor] + np.sqrt(1 - rho_theta) * own
        theta[i] = stats.beta.ppf(special.ndtr(latent), m.credibility.alpha, m.credibility.beta)
    return theta


def draw_execution(
    theta: np.ndarray,
    measures: Sequence[Measure],
    *,
    n_years: int,
    seed: int,
    replica: int,
    rho: float = DEFAULT_RHO,
) -> np.ndarray:
    """Boolean array (n_measures, n_years): whether each measure is executed each year.

    P(executed) equals theta exactly for every measure and year; rho only correlates failures
    of measures that share an executor.
    """
    _check_unique(measures)
    theta = np.asarray(theta, dtype=float)
    if theta.shape != (len(measures),):
        raise ValueError(f"theta must have shape ({len(measures)},), got {theta.shape}")
    if np.any((theta < 0) | (theta > 1)) or not np.all(np.isfinite(theta)):
        raise ValueError("theta must lie in [0, 1]")
    if not 0 <= rho < 1:
        raise ValueError("rho must lie in [0, 1)")
    if n_years < 0:
        raise ValueError("n_years must be non-negative")

    shocks: dict[str, np.ndarray] = {}
    for m in measures:
        if m.executor not in shocks:
            shocks[m.executor] = _stream(seed, replica, "shock", m.executor).standard_normal(
                n_years
            )

    executed = np.empty((len(measures), n_years), dtype=bool)
    thresholds = special.ndtri(theta)  # -inf for theta=0, +inf for theta=1
    for i, m in enumerate(measures):
        own = _stream(seed, replica, "eps", m.id).standard_normal(n_years)
        latent = np.sqrt(rho) * shocks[m.executor] + np.sqrt(1 - rho) * own
        executed[i] = latent < thresholds[i]
    return executed


def _check_unique(measures: Sequence[Measure]) -> None:
    ids = [m.id for m in measures]
    if len(set(ids)) != len(ids):
        raise ValueError("measure ids must be unique")
