"""Air mechanism: emissions per commune and source -> PM2.5 per commune, coupled across the basin.

Linear source-receptor model:

    C[r] = b + sum_s k_s * sum_c T[r, c] * E[c, s]

- C[r]: annual mean PM2.5 at receptor commune r (ug/m3).
- E[c, s]: primary PM2.5 emissions of commune c from source s (t/year), columns in SOURCES order.
- T[r, c]: transfer weight from commune c to commune r. Off-diagonal weights are the coupling:
  emissions in one commune change the air of the others.
- b: regional background (secondary aerosol, external input). k_s: ug/m3 per weighted t/year.

The core only applies the operator. How T, b and k_s are estimated lives in experiments/
(calibration), so the transport kernel can be improved without touching this module.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.estado import SOURCES

EARTH_RADIUS_KM = 6371.0


def distance_matrix_km(
    lat: np.ndarray,
    lon: np.ndarray,
    lat_to: np.ndarray | None = None,
    lon_to: np.ndarray | None = None,
) -> np.ndarray:
    """Great-circle (haversine) distance in km, shape (len(lat), len(lat_to)).

    Without `lat_to`/`lon_to`, distances between every pair of the first set.
    """
    if (lat_to is None) != (lon_to is None):
        raise ValueError("give both lat_to and lon_to, or neither")
    lat_a, lon_a = _radians(lat, lon)
    lat_b, lon_b = (lat_a, lon_a) if lat_to is None else _radians(lat_to, lon_to)
    dphi = lat_a[:, None] - lat_b[None, :]
    dlmb = lon_a[:, None] - lon_b[None, :]
    a = (
        np.sin(dphi / 2) ** 2
        + np.cos(lat_a[:, None]) * np.cos(lat_b[None, :]) * np.sin(dlmb / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _radians(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    if lat.shape != lon.shape or lat.ndim != 1:
        raise ValueError("lat and lon must be 1-D arrays of the same length")
    return np.radians(lat), np.radians(lon)


def exponential_transfer(distance_km: np.ndarray, scale_km: float) -> np.ndarray:
    """Isotropic kernel T = exp(-d / L). v0 of the transfer matrix (no wind, no relief)."""
    if not scale_km > 0:
        raise ValueError("scale_km must be positive")
    distance_km = np.asarray(distance_km, dtype=float)
    if np.any(distance_km < 0):
        raise ValueError("distances must be non-negative")
    return np.exp(-distance_km / scale_km)


@dataclass(frozen=True)
class AirModel:
    """Linear operator. `offset` (optional, per commune) anchors levels to measurements: where a
    station exists, observed minus modelled at that station; elsewhere 0. It shifts levels but
    never the change caused by emissions, so policy effects are the same with or without it.
    """

    transfer: np.ndarray
    background: float
    coefficients: np.ndarray
    offset: np.ndarray | None = None

    def __post_init__(self) -> None:
        t = self.transfer
        if t.ndim != 2 or t.shape[0] != t.shape[1]:
            raise ValueError("transfer must be a square matrix")
        if not np.all(np.isfinite(t)) or np.any(t < 0):
            raise ValueError("transfer must be finite and non-negative")
        if self.coefficients.shape != (len(SOURCES),):
            raise ValueError(f"coefficients must have shape ({len(SOURCES)},)")
        if np.any(self.coefficients < 0) or not self.background >= 0:
            raise ValueError("background and coefficients must be non-negative")
        if self.offset is not None and (self.offset.shape != (t.shape[0],)
                                        or not np.all(np.isfinite(self.offset))):
            raise ValueError(f"offset must be finite with shape ({t.shape[0]},)")

    @property
    def n_communes(self) -> int:
        return self.transfer.shape[0]

    def _check(self, emissions: np.ndarray) -> np.ndarray:
        emissions = np.asarray(emissions, dtype=float)
        if emissions.shape != (self.n_communes, len(SOURCES)):
            raise ValueError(
                f"emissions must have shape ({self.n_communes}, {len(SOURCES)}), "
                f"got {emissions.shape}"
            )
        return emissions

    def by_source(self, emissions: np.ndarray) -> np.ndarray:
        """(n_communes, n_sources): ug/m3 each source adds at each receptor."""
        emissions = self._check(emissions)
        return (self.transfer @ emissions) * self.coefficients

    def by_origin(self, emissions: np.ndarray) -> np.ndarray:
        """(receptor, origin): ug/m3 that each origin commune's emissions add at each receptor."""
        emissions = self._check(emissions)
        return self.transfer * (emissions @ self.coefficients)[None, :]

    def concentration(self, emissions: np.ndarray) -> np.ndarray:
        """Annual mean PM2.5 per commune (ug/m3): background + offset + all sources."""
        level = self.background + self.by_source(emissions).sum(axis=1)
        return level if self.offset is None else level + self.offset
