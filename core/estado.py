"""State of the region at one simulated year. Pure data: no dynamics live here."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Emission sources of the air mechanism (docs/contexto-proyecto.md, section 4).
SOURCES: tuple[str, ...] = ("heating", "transport", "industry")


@dataclass(frozen=True)
class RegionState:
    """Per-commune state, stored as aligned arrays (one position per commune).

    year: simulated calendar year.
    codes: official commune codes, in the order used by every array.
    pm25: annual mean PM2.5 concentration per commune (ug/m3).
    population: inhabitants per commune.
    emissions: shape (n_communes, len(SOURCES)); annual emissions per commune and source.
    """

    year: int
    codes: tuple[str, ...]
    pm25: np.ndarray
    population: np.ndarray
    emissions: np.ndarray

    def __post_init__(self) -> None:
        n = len(self.codes)
        if len(set(self.codes)) != n:
            raise ValueError("commune codes must be unique")
        if self.pm25.shape != (n,):
            raise ValueError(f"pm25 must have shape ({n},), got {self.pm25.shape}")
        if self.population.shape != (n,):
            raise ValueError(f"population must have shape ({n},), got {self.population.shape}")
        if self.emissions.shape != (n, len(SOURCES)):
            raise ValueError(
                f"emissions must have shape ({n}, {len(SOURCES)}), got {self.emissions.shape}"
            )
        for name in ("pm25", "population", "emissions"):
            arr = getattr(self, name)
            if not np.all(np.isfinite(arr)) or np.any(arr < 0):
                raise ValueError(f"{name} must be finite and non-negative")

    @property
    def n_communes(self) -> int:
        return len(self.codes)

    @property
    def total_population(self) -> float:
        return float(self.population.sum())

    def advance(
        self,
        *,
        pm25: np.ndarray | None = None,
        population: np.ndarray | None = None,
        emissions: np.ndarray | None = None,
    ) -> RegionState:
        """Return the next year's state; arrays not given carry over unchanged."""
        return RegionState(
            year=self.year + 1,
            codes=self.codes,
            pm25=self.pm25 if pm25 is None else pm25,
            population=self.population if population is None else population,
            emissions=self.emissions if emissions is None else emissions,
        )
