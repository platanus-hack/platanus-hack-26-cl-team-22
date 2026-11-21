"""Spatial-temporal transformation descriptors for dynamic map transitions.

Computes paired differences (active scenario minus reference scenario) across Monte Carlo
replicas, identifies focus communes, intensity timelines in [0, 1], uncertainty spread, and
geographic epicenter/bounding box — without embedding UI animation logic in the kernel.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

Direction = Literal["mejora", "empeora", "neutro"]
BetterDirection = Literal["menor", "mayor"]

_EPS = 1e-9


@dataclass(frozen=True)
class CommuneTransformation:
    """Year-by-year paired effect and uncertainty for one focus commune."""

    codigo: str
    direccion: Direction
    delta_p50: tuple[float, ...]
    incertidumbre: tuple[float, ...]
    intensidad: tuple[float, ...]


@dataclass(frozen=True)
class ScenarioTransformation:
    """Precomputed transformation descriptor for one scenario relative to a reference."""

    scenario_id: str
    referencia: str
    variable: str
    tipo: str
    max_abs_delta: float
    epicentro_lat: float
    epicentro_lon: float
    bbox: tuple[float, float, float, float]
    intensidad_regional: tuple[float, ...]
    comunas_foco: tuple[CommuneTransformation, ...]
    aviso: str | None = None


UNVALIDATED_PATTERN = ("Patrón entre comunas no validado: repartir el mismo cambio en todas "
                       "predice igual (make validate). Solo se muestra el cambio de la región.")


def compute_scenario_transformation(
    scenario_id: str,
    reference_id: str,
    variable: str,
    tipo: str,
    better: BetterDirection,
    active_runs: np.ndarray,
    reference_runs: np.ndarray,
    codes: Sequence[str],
    lat: np.ndarray,
    lon: np.ndarray,
    *,
    min_intensity: float = 0.05,
    espacial: bool = True,
) -> ScenarioTransformation:
    """Derive spatial-temporal transformation metadata from paired Monte Carlo runs.

    espacial=False is for variables whose pattern across communes is not validated (PM2.5:
    `make validate` shows the same change everywhere predicts as well). Then no focus communes
    are published, the epicentre and bbox cover the whole region, and `aviso` says why.
    """
    if better not in ("menor", "mayor"):
        raise ValueError(f"better must be 'menor' or 'mayor', got {better!r}")
    if not 0.0 <= min_intensity <= 1.0:
        raise ValueError("min_intensity must lie in [0, 1]")

    act = np.asarray(active_runs, dtype=float)
    ref = np.asarray(reference_runs, dtype=float)
    if act.ndim != 3 or act.shape != ref.shape:
        raise ValueError(
            f"active_runs and reference_runs must share 3-D shape, got {act.shape} vs {ref.shape}"
        )
    _, n_years, n_communes = act.shape
    if n_years < 1 or n_communes < 1:
        raise ValueError("runs must have at least 1 year and 1 commune")

    lat_arr = np.asarray(lat, dtype=float)
    lon_arr = np.asarray(lon, dtype=float)
    if len(codes) != n_communes or lat_arr.shape != (n_communes,) or lon_arr.shape != (n_communes,):
        raise ValueError("codes, lat, and lon must align with the commune dimension")

    diff = act - ref
    q10, q50, q90 = np.quantile(diff, [0.1, 0.5, 0.9], axis=0)
    spread = np.maximum(0.0, q90 - q10)

    abs_q50 = np.abs(q50)
    max_abs = float(np.max(abs_q50))
    intensity = abs_q50 / max_abs if max_abs > _EPS else np.zeros_like(abs_q50)

    yearly_mean_abs = np.mean(abs_q50, axis=1)
    max_mean = float(np.max(yearly_mean_abs))
    if max_mean > _EPS:
        regional_intensity = tuple(
            float(np.clip(v / max_mean, 0.0, 1.0)) for v in yearly_mean_abs
        )
    else:
        regional_intensity = tuple(0.0 for _ in range(n_years))

    focus_pairs: list[tuple[int, CommuneTransformation]] = []
    if espacial and max_abs > _EPS:
        for i, code in enumerate(codes):
            peak = float(np.max(intensity[:, i]))
            if peak < min_intensity:
                continue
            d_final = float(q50[-1, i])
            if abs(d_final) < _EPS:
                direction: Direction = "neutro"
            elif better == "menor":
                direction = "mejora" if d_final < 0 else "empeora"
            else:
                direction = "mejora" if d_final > 0 else "empeora"

            focus_pairs.append(
                (
                    i,
                    CommuneTransformation(
                        codigo=code,
                        direccion=direction,
                        delta_p50=tuple(float(x) for x in q50[:, i]),
                        incertidumbre=tuple(float(x) for x in spread[:, i]),
                        intensidad=tuple(float(np.clip(x, 0.0, 1.0)) for x in intensity[:, i]),
                    ),
                )
            )

    focus_pairs.sort(
        key=lambda pair: (
            -abs(pair[1].delta_p50[-1]),
            -max(pair[1].intensidad),
            pair[1].codigo,
        )
    )
    focus_items = tuple(item for _, item in focus_pairs)

    if focus_pairs:
        idx = np.array([i for i, _ in focus_pairs], dtype=int)
        # Intensity is unitless in [0, 1]; mixing it with the change would make the weight
        # depend on the variable's units.
        weights = np.array([max(max(item.intensidad), 1e-12) for _, item in focus_pairs],
                           dtype=float)
        total_w = float(np.sum(weights))
        epicentro_lat = float(np.sum(lat_arr[idx] * weights) / total_w)
        epicentro_lon = float(np.sum(lon_arr[idx] * weights) / total_w)
        bbox = (
            float(np.min(lon_arr[idx])),
            float(np.min(lat_arr[idx])),
            float(np.max(lon_arr[idx])),
            float(np.max(lat_arr[idx])),
        )
    else:
        epicentro_lat = float(np.mean(lat_arr))
        epicentro_lon = float(np.mean(lon_arr))
        bbox = (
            float(np.min(lon_arr)),
            float(np.min(lat_arr)),
            float(np.max(lon_arr)),
            float(np.max(lat_arr)),
        )

    return ScenarioTransformation(
        scenario_id=scenario_id,
        referencia=reference_id,
        variable=variable,
        tipo=tipo,
        max_abs_delta=max_abs if max_abs > _EPS else 0.0,
        epicentro_lat=epicentro_lat,
        epicentro_lon=epicentro_lon,
        bbox=bbox,
        intensidad_regional=regional_intensity,
        comunas_foco=focus_items,
        aviso=None if espacial else UNVALIDATED_PATTERN,
    )


def serialize_transformations(
    items: Sequence[ScenarioTransformation],
    *,
    default_reference: str = "base",
) -> dict[str, object]:
    """Serialize ScenarioTransformation items into simulacion.json['transformaciones']."""
    por_escenario: dict[str, dict[str, object]] = {}
    for item in items:
        por_escenario[item.scenario_id] = {
            "referencia": item.referencia,
            "variable": item.variable,
            "tipo": item.tipo,
            "max_abs_delta": round(item.max_abs_delta, 3),
            "epicentro": {
                "lat": round(item.epicentro_lat, 5),
                "lon": round(item.epicentro_lon, 5),
            },
            "bbox": [round(v, 5) for v in item.bbox],
            "intensidad_regional": [round(v, 3) for v in item.intensidad_regional],
            "comunas_foco": [
                {
                    "codigo": c.codigo,
                    "direccion": c.direccion,
                    "delta_p50": [round(v, 3) for v in c.delta_p50],
                    "incertidumbre": [round(v, 3) for v in c.incertidumbre],
                    "intensidad": [round(v, 3) for v in c.intensidad],
                }
                for c in item.comunas_foco
            ],
        }
        if item.aviso:
            por_escenario[item.scenario_id]["aviso"] = item.aviso
    return {
        "referencia_por_defecto": default_reference,
        "por_escenario": por_escenario,
    }
