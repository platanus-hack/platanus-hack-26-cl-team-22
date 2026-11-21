"""Can the air model tell communes apart? Tests of candidate v1 improvements over v0.

Every candidate is scored by leave-one-station-out RMSE on 2023 annual means (10 stations),
with its free parameters chosen without the held-out station (nested), against v0 and against
"mean of the other stations". A candidate is adopted only if it beats v0.

1. Seasonal: separate winter (May-Aug) and rest-of-year equations, leña only in winter.
2. Wind: transfer weighted towards communes downwind of each source, using 2023 SINCA wind
   roses (data/aire/viento_rosa_2023.csv), one extra parameter alpha.
3. Residual interpolation: v0 plus inverse-distance interpolation of the other stations'
   residuals (can levels be inferred where there is no station?).
4. Anchoring (temporal): predict 2024 at each station as v0 plus that station's own 2023
   residual, against v0 alone and persistence.

Usage:  python -m experiments.aire_v1_pruebas
Output: results/aire_v1_pruebas.json
"""
from __future__ import annotations

import csv
import json

import numpy as np
from scipy.optimize import nnls

from core.aire import distance_matrix_km, exponential_transfer
from core.estado import SOURCES
from experiments.datos_aire import ROOT, load_communes, load_emissions, load_stations

OUTPUT = ROOT / "results" / "aire_v1_pruebas.json"
WIND = ROOT / "data" / "aire" / "viento_rosa_2023.csv"
STATION_META = ROOT / "data" / "aire" / "estaciones.csv"
YEAR = 2023
SCALES = (3.0, 5.0, 8.0, 12.0, 18.0, 25.0, 40.0)
ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
WINTER_DAYS, YEAR_DAYS = 123, 365
MODELLED = [SOURCES.index(s) for s in ("heating", "transport", "industry")]


def rmse(x) -> float:
    return round(float(np.sqrt(np.mean(np.square(x)))), 3)


def fit(design: np.ndarray, y: np.ndarray) -> np.ndarray:
    return nnls(design, y)[0]


def bearing_deg(lat1, lon1, lat2, lon2):
    """Bearing from point 1 to point 2, degrees clockwise from north (flat approximation)."""
    y = (lon2 - lon1) * np.cos(np.radians((lat1 + lat2) / 2))
    return np.degrees(np.arctan2(y, lat2 - lat1)) % 360


def load_roses() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    by_station: dict[str, list[tuple[float, float]]] = {}
    with WIND.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            by_station.setdefault(r["estacion_id"], []).append(
                (float(r["sector_centro_grados"]), float(r["frecuencia"])))
    return {k: (np.array([c for c, _ in v]), np.array([f for _, f in v]))
            for k, v in by_station.items()}


def main() -> None:
    communes = load_communes()
    emissions, _ = load_emissions(communes.codes, YEAR)
    total = emissions[:, MODELLED].sum(axis=1)
    heating = emissions[:, SOURCES.index("heating")]
    rest = total - heating
    st = load_stations(YEAR)
    winter = load_stations(YEAR, "pm25_media_invierno").pm25
    obs = st.pm25
    n = len(obs)
    dist = distance_matrix_km(st.lat, st.lon, communes.lat, communes.lon)

    def nested(predict, grid) -> float:
        """Choose the grid point on n-1 stations, predict the held-out one."""
        errors = []
        for j in range(n):
            train = np.arange(n) != j
            best = min(grid, key=lambda g: rmse(loo_errors(predict, g, train)))
            errors.append(predict(best, train, j) - obs[j])
        return rmse(errors)

    def loo_errors(predict, g, mask):
        out = []
        for j in np.flatnonzero(mask):
            train = mask.copy()
            train[j] = False
            out.append(predict(g, train, j) - obs[j])
        return out

    # v0: C = b + k * T(L) @ total
    def v0(g, train, j):
        s = exponential_transfer(dist, g[0]) @ total
        b, k = fit(np.column_stack([np.ones(train.sum()), s[train]]), obs[train])
        return b + k * s[j]

    grid_v0 = [(L,) for L in SCALES]

    # 1. Seasonal
    rest_of_year = (YEAR_DAYS * obs - WINTER_DAYS * winter) / (YEAR_DAYS - WINTER_DAYS)

    def seasonal(g, train, j):
        t = exponential_transfer(dist, g[0])
        lena, other = t @ heating, t @ rest
        m = int(train.sum())
        a = np.zeros((2 * m, 4))
        a[:m, 0], a[m:, 1] = 1, 1
        a[:m, 2] = lena[train] * YEAR_DAYS / WINTER_DAYS + other[train]
        a[m:, 3] = other[train]
        bw, bn, kw, kn = fit(a, np.r_[winter[train], rest_of_year[train]])
        w = bw + kw * (lena[j] * YEAR_DAYS / WINTER_DAYS + other[j])
        r = bn + kn * other[j]
        return (WINTER_DAYS * w + (YEAR_DAYS - WINTER_DAYS) * r) / YEAR_DAYS

    # 2. Wind
    roses = load_roses()
    with STATION_META.open(encoding="utf-8-sig") as fh:
        meta = {r["estacion_id"]: r for r in csv.DictReader(fh)}
    rose_ids = sorted(roses)
    rlat = np.array([float(meta[s]["lat"]) for s in rose_ids])
    rlon = np.array([float(meta[s]["lon"]) for s in rose_ids])
    nearest = distance_matrix_km(communes.lat, communes.lon, rlat, rlon).argmin(axis=1)
    directional = np.ones_like(dist)
    for c in range(len(communes.codes)):
        centre, freq = roses[rose_ids[nearest[c]]]
        downwind = (centre + 180) % 360
        b = bearing_deg(communes.lat[c], communes.lon[c], st.lat, st.lon)
        cos = np.cos(np.radians(b[:, None] - downwind[None, :]))
        directional[:, c] = np.pi * (np.maximum(cos, 0) * freq[None, :]).sum(axis=1)

    def wind(g, train, j):
        s = (exponential_transfer(dist, g[0]) * ((1 - g[1]) + g[1] * directional)) @ total
        b, k = fit(np.column_stack([np.ones(train.sum()), s[train]]), obs[train])
        return b + k * s[j]

    grid_wind = [(L, a) for L in SCALES for a in ALPHAS]

    # 3. Residual interpolation (inverse distance, power 1)
    between = distance_matrix_km(st.lat, st.lon)

    def interpolated(g, train, j):
        s = exponential_transfer(dist, g[0]) @ total
        b, k = fit(np.column_stack([np.ones(train.sum()), s[train]]), obs[train])
        residual = obs[train] - (b + k * s[train])
        w = 1 / np.maximum(between[j, train], 0.5)
        return b + k * s[j] + (w * residual).sum() / w.sum()

    mean_others = rmse([(obs.sum() - obs[j]) / (n - 1) - obs[j] for j in range(n)])

    # 4. Anchoring: 2024 levels from v0 plus each station's 2023 residual
    scale = 40.0
    s23 = exponential_transfer(dist, scale) @ total
    b, k = fit(np.column_stack([np.ones(n), s23]), obs)
    residual23 = dict(zip(st.ids, obs - (b + k * s23), strict=True))
    st24 = load_stations(2024)
    e24, _ = load_emissions(communes.codes, 2024)
    for src in ("transport", "industry"):  # 2024 transport missing; industry 2024 has the
        e24[:, SOURCES.index(src)] = emissions[:, SOURCES.index(src)]  # Las Condes artifact
    s24 = exponential_transfer(distance_matrix_km(st24.lat, st24.lon, communes.lat,
                                                  communes.lon), scale) @ e24[:, MODELLED].sum(1)
    both = [j for j, sid in enumerate(st24.ids) if sid in residual23]
    observed24 = st24.pm25[both]
    plain = b + k * s24[both]
    anchored = plain + np.array([residual23[st24.ids[j]] for j in both])
    persistence = np.array([obs[list(st.ids).index(st24.ids[j])] for j in both])

    results = {
        "comando": "python -m experiments.aire_v1_pruebas",
        "estaciones": n,
        "loo_rmse": {
            "v0": nested(v0, grid_v0),
            "media_de_las_otras": mean_others,
            "estacional": nested(seasonal, grid_v0),
            "viento": nested(wind, grid_wind),
            "v0_mas_residuos_interpolados": nested(interpolated, grid_v0),
        },
        "niveles_2024": {
            "estaciones": len(both),
            "v0": rmse(plain - observed24),
            "v0_anclado_al_residuo_2023": rmse(anchored - observed24),
            "persistencia": rmse(persistence - observed24),
        },
        "rosas_de_viento": {"archivo": "data/aire/viento_rosa_2023.csv",
                            "estaciones": rose_ids},
        "supuestos": [
            ("Industry and transport 2024 use the 2023 values (transport missing in 2024; "
             "industry 2024 has the Las Condes jump)."),
            "Each source commune uses the wind rose of its nearest station with wind data.",
        ],
    }
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: results[k] for k in ("loo_rmse", "niveles_2024")}, indent=1))
    print(f"\n{OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
