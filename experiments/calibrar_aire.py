"""Calibrate and test the v0 air model (isotropic kernel) against SINCA stations.

Model (core/aire.py):  C[station] = b + k * sum_c exp(-d(station, c) / L) * E_total[c]

- Fit on 2023 (the only year with all four RETC sources): L by leave-one-station-out error,
  then b and a single k shared by all sources by non-negative least squares. One k for all
  sources is a physical choice: emissions are all tonnes of primary PM2.5.
- Test on data the fit never saw:
  * 2024 levels per station.
  * Change 2017 -> 2023 per station, the closest thing to a policy response we can measure.
- Every metric is compared against simple alternatives (see docs/modelo-aire.md).

Usage:  python -m experiments.calibrar_aire
Output: results/aire_calibracion.json (parameters read by the simulation, metrics, assumptions).
"""
from __future__ import annotations

import csv
import json
import unicodedata

import numpy as np
from scipy.optimize import nnls

from core.aire import distance_matrix_km, exponential_transfer
from core.estado import SOURCES
from experiments.datos_aire import (
    F_ESTACIONES,
    ROOT,
    load_communes,
    load_emissions,
    load_stations,
)

FIT_YEAR = 2023
SCALES_KM = (3.0, 5.0, 8.0, 12.0, 18.0, 25.0, 40.0)
OUTPUT = ROOT / "results" / "aire_calibracion.json"
TRANSPORT = SOURCES.index("transport")
# Sources the v0 model transports. "other" (wildfires, burning) is episodic: 30,842 t in 2017
# against 1,855 t in 2023, mostly summer fires that do not move the annual mean in proportion.
# It stays in the state with coefficient 0 until it gets its own treatment.
MODELLED = np.array([s != "other" for s in SOURCES])

ASSUMPTIONS = [
    "Transport emissions exist only for 2023; 2017 and 2024 reuse the 2023 values.",
    "A commune absent from the RETC table for a source is counted as 0 t/year.",
    "Stations are receptors at their own coordinates; emissions sit at commune centroids.",
    "Annual means only; no seasonal background, wind or relief (v0).",
    "Source 'other' (wildfires, agricultural burning) has coefficient 0: it is episodic.",
    "RETC industry coverage changes between years (110 t in 2017, 616 t in 2024).",
]


def rmse(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def fit(signal: np.ndarray, observed: np.ndarray) -> tuple[float, float]:
    coef, _ = nnls(np.column_stack([np.ones_like(signal), signal]), observed)
    return float(coef[0]), float(coef[1])


def loo_errors(signal: np.ndarray, observed: np.ndarray) -> np.ndarray:
    errors = []
    for i in range(len(observed)):
        rest = np.arange(len(observed)) != i
        b, k = fit(signal[rest], observed[rest])
        errors.append(b + k * signal[i] - observed[i])
    return np.array(errors)


def loo_mean_errors(observed: np.ndarray) -> np.ndarray:
    n = len(observed)
    return np.array([(observed.sum() - observed[i]) / (n - 1) - observed[i] for i in range(n)])


def main() -> None:
    communes = load_communes()
    emissions = {}
    missing = {}
    for year in (2017, FIT_YEAR, 2024):
        emissions[year], missing[year] = load_emissions(communes.codes, year)
    for year in (2017, 2024):
        emissions[year][:, TRANSPORT] = emissions[FIT_YEAR][:, TRANSPORT]
    total = {year: e[:, MODELLED].sum(axis=1) for year, e in emissions.items()}

    def signal(stations, scale_km, year):
        d = distance_matrix_km(stations.lat, stations.lon, communes.lat, communes.lon)
        return exponential_transfer(d, scale_km) @ total[year]

    # --- Fit on 2023 ---
    st = load_stations(FIT_YEAR)
    by_scale = {L: rmse(loo_errors(signal(st, L, FIT_YEAR), st.pm25)) for L in SCALES_KM}
    scale = min(by_scale, key=by_scale.get)
    background, k = fit(signal(st, scale, FIT_YEAR), st.pm25)
    pred_fit = background + k * signal(st, scale, FIT_YEAR)
    r2 = 1 - np.sum((st.pm25 - pred_fit) ** 2) / np.sum((st.pm25 - st.pm25.mean()) ** 2)

    # Anchoring: each station's residual, assigned to the commune it sits in. The simulation
    # adds it to that commune's level (measured level + modelled change).
    def plain(name: str) -> str:
        text = unicodedata.normalize("NFKD", name)
        return "".join(ch for ch in text if not unicodedata.combining(ch)).lower().strip()

    with F_ESTACIONES.open(encoding="utf-8-sig", newline="") as fh:
        station_commune = {r["estacion_id"]: r["comuna"] for r in csv.DictReader(fh)}
    code_of = {plain(name): code for name, code in zip(communes.names, communes.codes,
                                                       strict=True)}
    # The residual is taken against the model at the commune centroid, which is where the
    # simulation evaluates the commune, so an anchored commune starts exactly at its measurement.
    centroid_model = background + k * (
        exponential_transfer(distance_matrix_km(communes.lat, communes.lon), scale)
        @ total[FIT_YEAR])
    anchoring: dict[str, dict] = {}
    for sid, observed in zip(st.ids, st.pm25, strict=True):
        code = code_of[plain(station_commune[sid])]
        if code in anchoring:
            raise SystemExit(f"Two stations in commune {code}: decide how to anchor it")
        modelled = centroid_model[communes.codes.index(code)]
        anchoring[code] = {"estacion_id": sid, "medido_ugm3": round(float(observed), 3),
                           "residuo_ugm3": round(float(observed - modelled), 3)}

    def predict(stations, year):
        return background + k * signal(stations, scale, year)

    # --- Test 1: 2024 levels ---
    st24 = load_stations(2024)
    prev = dict(zip(st.ids, st.pm25, strict=True))
    both = [i for i, sid in enumerate(st24.ids) if sid in prev]
    persistence = np.array([prev[st24.ids[i]] for i in both]) - st24.pm25[both]
    test_2024 = {
        "stations": len(st24.ids),
        "rmse_model": rmse(predict(st24, 2024) - st24.pm25),
        "rmse_mean_of_other_stations": rmse(loo_mean_errors(st24.pm25)),
        "rmse_persistence_2023": rmse(persistence),
        "stations_with_persistence": len(both),
    }

    # --- Test 2: change 2017 -> 2023 per station ---
    st17 = load_stations(2017)
    obs17 = dict(zip(st17.ids, st17.pm25, strict=True))
    common = [i for i, sid in enumerate(st.ids) if sid in obs17]
    observed_change = st.pm25[common] - np.array([obs17[st.ids[i]] for i in common])
    predicted_change = (predict(st, FIT_YEAR) - predict(st, 2017))[common]
    change = {
        "stations": len(common),
        "observed_mean": float(observed_change.mean()),
        "predicted_mean": float(predicted_change.mean()),
        "rmse_model": rmse(predicted_change - observed_change),
        "rmse_no_change": rmse(observed_change),
        "rmse_same_change_everywhere": rmse(observed_change - observed_change.mean()),
        "pattern_correlation": float(np.corrcoef(predicted_change, observed_change)[0, 1])
        if len(common) > 2 else None,
    }

    result = {
        "command": "python -m experiments.calibrar_aire",
        "model": "v0 isotropic exponential kernel (core/aire.py)",
        "parameters": {
            "scale_km": scale,
            "background_ugm3": background,
            "k_ugm3_per_t": k,
            "coefficients_by_source": {s: (k if m else 0.0) for s, m in zip(SOURCES, MODELLED, strict=True)},
            "fit_year": FIT_YEAR,
        },
        "fit": {
            "stations": len(st.ids),
            "r2": float(r2),
            "loo_rmse_by_scale_km": by_scale,
            "loo_rmse_model": by_scale[scale],
            "loo_rmse_mean_of_other_stations": rmse(loo_mean_errors(st.pm25)),
            "scale_at_grid_edge": scale == max(SCALES_KM),
        },
        "test_2024_levels": test_2024,
        "test_change_2017_2023": change,
        "anchoring": {
            "year": FIT_YEAR,
            "note": ("Residual (observed at the station - modelled at the commune centroid), "
                     "so an anchored commune starts at its measured level; communes without a "
                     "station get 0."),
            "communes": anchoring,
        },
        "assumptions": ASSUMPTIONS,
        "missing_emissions": {
            str(y): {s: len(c) for s, c in m.items() if c} for y, m in missing.items()
        },
        "data": ["data/comunas_rm.csv", "data/emisiones/pm25_por_comuna_fuente.csv",
                 "data/aire/estaciones.csv", "data/aire/pm25_anual.csv"],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k_: result[k_] for k_ in ("parameters", "fit", "test_2024_levels",
                                                 "test_change_2017_2023")}, indent=2))
    print(f"\nWritten {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
