"""Households mechanism: people move between communes each year.

Aggregated flows, calibrated with the census question "commune of residence 5 years ago":

    out[i]      = population[i] * r[i]                   (inertia: most people stay)
    flow[i, j]  = out[i] * share[i, j]                   (j != i, shares of the fitting matrix)
    population' = population - out + inflow, limited by housing capacity

- r[i]: annual out-rate from the 5-year rate R5[i], assuming a constant hazard:
  r = 1 - (1 - R5) ** (1 / 5).
- share[i, j]: where the people leaving commune i went, as observed in the census.

The system is closed: births, deaths and moves from or to outside the region are not modelled,
so the regional total is conserved exactly. Air does not change destinations (not identifiable
from the census; see docs/modelo-hogares.md).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MigrationModel:
    out_rate: np.ndarray  # annual, per commune
    shares: np.ndarray  # (origin, destination), zero diagonal, rows sum to 1 or 0

    def __post_init__(self) -> None:
        n = self.out_rate.shape[0]
        if self.out_rate.shape != (n,) or self.shares.shape != (n, n):
            raise ValueError("out_rate must be (n,) and shares (n, n)")
        if np.any((self.out_rate < 0) | (self.out_rate > 1)):
            raise ValueError("out_rate must lie in [0, 1]")
        if np.any(self.shares < 0) or np.any(np.diag(self.shares) != 0):
            raise ValueError("shares must be non-negative with a zero diagonal")
        sums = self.shares.sum(axis=1)
        if not np.all(np.isclose(sums, 1.0) | np.isclose(sums, 0.0)):
            raise ValueError("each row of shares must sum to 1 (or 0 if nobody leaves)")

    @property
    def n_communes(self) -> int:
        return self.out_rate.shape[0]

    @classmethod
    def from_census(cls, matrix: np.ndarray, years: int = 5) -> MigrationModel:
        """Build from a census matrix (origin = residence `years` ago, destination = now)."""
        matrix = np.asarray(matrix, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or np.any(matrix < 0):
            raise ValueError("matrix must be square and non-negative")
        total = matrix.sum(axis=1)
        leaving = total - np.diag(matrix)
        rate_period = np.divide(leaving, total, out=np.zeros_like(total), where=total > 0)
        out_rate = 1.0 - (1.0 - rate_period) ** (1.0 / years)
        off = matrix.copy()
        np.fill_diagonal(off, 0.0)
        shares = np.divide(off, leaving[:, None], out=np.zeros_like(off),
                           where=leaving[:, None] > 0)
        return cls(out_rate, shares)

    def step(
        self, population: np.ndarray, capacity: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """One year. Returns (new population, flows[origin, destination]).

        With `capacity`, inflows to a full commune are scaled down so it does not exceed its
        capacity; people who cannot move stay where they are. The total is always conserved.
        """
        population = np.asarray(population, dtype=float)
        if population.shape != (self.n_communes,) or np.any(population < 0):
            raise ValueError(f"population must be non-negative with shape ({self.n_communes},)")
        flows = population[:, None] * self.out_rate[:, None] * self.shares
        if capacity is not None:
            capacity = np.asarray(capacity, dtype=float)
            if capacity.shape != population.shape:
                raise ValueError("capacity must have the same shape as population")
            after_out = population - flows.sum(axis=1)
            inflow = flows.sum(axis=0)
            room = np.maximum(capacity - after_out, 0.0)
            scale = np.divide(room, inflow, out=np.ones_like(inflow), where=inflow > 0)
            flows = flows * np.minimum(scale, 1.0)[None, :]
        new = population - flows.sum(axis=1) + flows.sum(axis=0)
        return new, flows

    def run(
        self, population: np.ndarray, n_years: int, capacity: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """(n_years + 1, n) populations, first row the initial one; (n_years, n, n) flows.

        capacity, if given, has shape (n_years, n): the limit for each simulated year.
        """
        if capacity is not None and np.shape(capacity) != (n_years, self.n_communes):
            raise ValueError(f"capacity must have shape ({n_years}, {self.n_communes})")
        populations = [np.asarray(population, dtype=float)]
        flows = []
        for t in range(n_years):
            new, f = self.step(populations[-1], None if capacity is None else capacity[t])
            populations.append(new)
            flows.append(f)
        return np.array(populations), np.array(flows).reshape(n_years, self.n_communes,
                                                              self.n_communes)


def net_migration(matrix: np.ndarray) -> np.ndarray:
    """Arrivals minus departures per commune, from an (origin, destination) flow matrix."""
    matrix = np.asarray(matrix, dtype=float)
    return matrix.sum(axis=0) - matrix.sum(axis=1)
