"""Does new housing explain where people move? Out-of-sample test with building permits.

Every model keeps the 2012-2017 annual out-rate of each comuna (core.hogares) and changes only
WHERE movers go. Parameters and the permit lag are chosen with the 2012->2017 matrix only; the
score is the same as experiments/calibrar_hogares.py: net migration per comuna over 2019->2024,
starting from the 2019 origins and running 5 annual steps.

Destination models:
- `proporciones_2012_2017`: observed shares (the model in production).
- `gravedad`: s[i, j] ∝ exp(a·log V[j] − b·d[i, j]); V = census 2017 dwellings.
- `gravedad_permisos`: adds + g·log(1 + P[j]/V[j]); P = housing permits in a 5-year window.
- `pivote_permisos`: observed shares × ((1 + P_test/V) / (1 + P_fit/V))^g, with g from
  `gravedad_permisos`. Keeps the observed structure and shifts it toward new supply.
- `radiacion`: parameter-free radiation model (Simini et al. 2012, doi:10.1038/nature10856)
  with census 2017 population.

Second test, allocation of arrivals from outside the RM (abroad and other regions):
- `reparto_2019_2024`: given the observed 2019-2024 RM totals, how well does each set of weights
  split them among comunas? Weights: 2012-2017 shares, permits 2016-2020 (lag 3, chosen above),
  permits known in 2019 (2014-2018), 2017 population. Isolates the split from the total.
- `poblacion_2017_2024`: the open model of experiments/validar_poblacion.py with the same RM
  arrival totals, split by permits 2012-2016 (known at the 2017 start) instead of fixed
  2012-2017 comuna rates.

Usage:  python -m experiments.validar_vivienda   -> results/vivienda_validacion.json
"""

from __future__ import annotations

import csv
import json

import numpy as np
from scipy.optimize import minimize

from core.aire import distance_matrix_km
from core.hogares import MigrationModel, net_migration
from experiments.datos_aire import ROOT, load_communes
from experiments.datos_hogares import load_moves, load_population_dwellings

YEARS = 5
LAGS = (0, 1, 2, 3, 5)
SALIDA = ROOT / "results" / "vivienda_validacion.json"


def _utilidad(theta, dist, log_stock, nuevas) -> np.ndarray:
    a, b, g = theta
    u = a * log_stock[None, :] - b * dist
    if nuevas is not None:
        u = u + g * np.log1p(nuevas)[None, :]
    return u


def shares_destinos(theta, dist, log_stock, nuevas) -> np.ndarray:
    """Row-stochastic destination shares with zero diagonal (origin-constrained logit)."""
    u = _utilidad(theta, dist, log_stock, nuevas)
    np.fill_diagonal(u, -np.inf)
    u = u - u.max(axis=1, keepdims=True)
    e = np.exp(u)
    return e / e.sum(axis=1, keepdims=True)


def ajustar_destinos(flujos, dist, log_stock, nuevas) -> tuple[float, float, float]:
    """Maximum likelihood (a, b, g) from an (origin, destination) flow matrix.

    The diagonal (stayers) is ignored. With `nuevas` None, g stays at 0.
    """
    f = np.asarray(flujos, dtype=float).copy()
    np.fill_diagonal(f, 0.0)

    def nll(x):
        theta = (x[0], x[1], x[2] if nuevas is not None else 0.0)
        u = _utilidad(theta, dist, log_stock, nuevas)
        np.fill_diagonal(u, -np.inf)
        m = u.max(axis=1, keepdims=True)
        lse = m[:, 0] + np.log(np.exp(u - m).sum(axis=1))
        u_finite = np.where(np.isfinite(u), u, 0.0)
        return -(np.sum(f * u_finite) - np.sum(f.sum(axis=1) * lse))

    x0 = np.array([1.0, 0.1, 0.0 if nuevas is None else 1.0])
    res = minimize(nll, x0, method="BFGS", options={"gtol": 1e-8, "maxiter": 2000})
    a, b, g = res.x
    return float(a), float(b), float(g) if nuevas is not None else 0.0


def pivote_por_permisos(shares, nuevas_prueba, nuevas_ajuste, gamma) -> np.ndarray:
    """Observed shares reweighted by the change in new supply of each destination."""
    factor = ((1 + np.asarray(nuevas_prueba)) / (1 + np.asarray(nuevas_ajuste))) ** gamma
    s = np.asarray(shares, dtype=float) * factor[None, :]
    np.fill_diagonal(s, 0.0)
    filas = s.sum(axis=1, keepdims=True)
    return np.divide(s, filas, out=np.zeros_like(s), where=filas > 0)


def radiacion(poblacion, dist) -> np.ndarray:
    """Radiation-model destination shares (no parameters), normalized per origin."""
    m = np.asarray(poblacion, dtype=float)
    dist = np.asarray(dist, dtype=float)
    n = m.shape[0]
    if dist.shape != (n, n):
        raise ValueError(f"dist must have shape ({n}, {n})")
    s = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dentro = (dist[i] < dist[i, j]) & (np.arange(n) != i) & (np.arange(n) != j)
            rodeo = m[dentro].sum()
            s[i, j] = m[i] * m[j] / ((m[i] + rodeo) * (m[i] + m[j] + rodeo))
    return s / s.sum(axis=1, keepdims=True)


def repartir(total: float, pesos: np.ndarray) -> np.ndarray:
    """Split `total` proportionally to non-negative `pesos` (all zero -> nothing)."""
    pesos = np.asarray(pesos, dtype=float)
    if np.any(pesos < 0):
        raise ValueError("weights must not be negative")
    suma = pesos.sum()
    return total * pesos / suma if suma > 0 else np.zeros_like(pesos)


def _externos(codes: tuple[str, ...], periodo: str, col: str) -> np.ndarray:
    with (ROOT / "data" / "censo" / "flujos_externos.csv").open(encoding="utf-8") as fh:
        filas = {r["codigo"]: r for r in csv.DictReader(fh) if r["periodo"] == periodo}
    return np.array([float(filas[c][col]) for c in codes])


def prueba_reparto(codes, permisos, pob17, viv17) -> dict:
    """Split the observed 2019-2024 arrivals with different weights; RMSE per comuna."""
    from experiments.validar_poblacion import ANIOS, TasasAbiertas, proyectar, tasas_2012_2017

    pesos = {
        "proporciones_2012_2017": None,
        "permisos_2016_2020": ventana(permisos, 2019, 3),
        "permisos_2014_2018": ventana(permisos, 2019, 5),
        "poblacion_2017": pob17,
    }
    reparto = {}
    for col in ("llegan_extranjero", "llegan_otras_regiones"):
        obs = _externos(codes, "2019-2024", col)
        base = _externos(codes, "2012-2017", col)
        reparto[col] = {"total_rm_observado": round(float(obs.sum()))}
        for nombre, w in pesos.items():
            pred = repartir(obs.sum(), base if w is None else w)
            reparto[col][f"rmse_{nombre}"] = round(float(np.sqrt(np.mean((pred - obs) ** 2))), 1)
            reparto[col][f"corr_{nombre}"] = round(float(np.corrcoef(pred, obs)[0, 1]), 3)

    pob24, _ = load_population_dwellings(codes, 2024)
    modelo = MigrationModel.from_census(load_moves(codes, "2012-2017"), years=YEARS)
    tasas = tasas_2012_2017(codes, pob17)
    w17 = sum(permisos[a] for a in range(2012, 2017))
    con_permisos = TasasAbiertas(
        natalidad=tasas.natalidad, mortalidad=tasas.mortalidad,
        llegan_regiones=repartir(float(tasas.llegan_regiones @ pob17), w17) / pob17,
        llegan_extranjero=repartir(float(tasas.llegan_extranjero @ pob17), w17) / pob17,
        salen_regiones=tasas.salen_regiones)
    poblacion = {}
    for nombre, t in (("abierto_tasas_2012_2017", tasas), ("abierto_llegadas_por_permisos",
                                                          con_permisos)):
        pred = proyectar(modelo, pob17, t, ANIOS)[-1]
        poblacion[nombre] = {"rmse_personas": round(float(np.sqrt(np.mean((pred - pob24) ** 2))),
                                                    1),
                             "total_rm_predicho": round(float(pred.sum()))}
    poblacion["sin_cambio"] = {"rmse_personas": round(float(np.sqrt(np.mean(
        (pob17 - pob24) ** 2))), 1), "total_rm_predicho": round(float(pob17.sum()))}
    return {"reparto_2019_2024": reparto, "poblacion_2017_2024": poblacion}


def _leer_permisos(codes: tuple[str, ...]) -> dict[int, np.ndarray]:
    por_anio: dict[int, dict[str, float]] = {}
    with (ROOT / "data" / "vivienda" / "permisos_vivienda.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            por_anio.setdefault(int(r["anio"]), {})[r["codigo"]] = float(r["viviendas"])
    return {a: np.array([v[c] for c in codes]) for a, v in por_anio.items()}


def ventana(permisos: dict[int, np.ndarray], inicio_periodo: int, lag: int) -> np.ndarray:
    """Permits in the 5 years starting `lag` years before the move period starts."""
    desde = inicio_periodo - lag
    return sum(permisos[a] for a in range(desde, desde + YEARS))


def _puntaje(pred, obs) -> dict:
    err = pred - obs
    return {"rmse_personas": round(float(np.sqrt(np.mean(err ** 2))), 1),
            "mae_personas": round(float(np.mean(np.abs(err))), 1),
            "correlacion": round(float(np.corrcoef(pred, obs)[0, 1]), 3)}


def main() -> None:
    com = load_communes()
    codes = com.codes
    fit = load_moves(codes, "2012-2017")
    test = load_moves(codes, "2019-2024")
    pob17, viv17 = load_population_dwellings(codes, 2017)
    dist = distance_matrix_km(com.lat, com.lon)
    log_v = np.log(viv17)
    permisos = _leer_permisos(codes)
    base = MigrationModel.from_census(fit, years=YEARS)
    observado = net_migration(test)

    def evaluar(shares) -> np.ndarray:
        pops, _ = MigrationModel(base.out_rate, shares).run(test.sum(axis=1), YEARS)
        return pops[-1] - pops[0]

    grav = ajustar_destinos(fit, dist, log_v, None)
    por_lag = {}
    for lag in LAGS:
        g_fit = ventana(permisos, 2012, lag) / viv17
        theta = ajustar_destinos(fit, dist, log_v, g_fit)
        s = shares_destinos(theta, dist, log_v, g_fit)
        f = fit.copy()
        np.fill_diagonal(f, 0)
        por_lag[lag] = {"theta": theta, "loglik": float(np.sum(f * np.log(
            np.where(s > 0, s, 1.0))))}
    lag = max(por_lag, key=lambda k: por_lag[k]["loglik"])

    resultados = {}
    for etiqueta, lag_usado in (("lag_elegido_en_ajuste", lag),
                                ("solo_permisos_conocidos_en_2019", 5)):
        theta = por_lag[lag_usado]["theta"]
        g_fit = ventana(permisos, 2012, lag_usado) / viv17
        g_test = ventana(permisos, 2019, lag_usado) / viv17
        modelos = {
            "proporciones_2012_2017": base.shares,
            "gravedad": shares_destinos(grav, dist, log_v, None),
            "gravedad_permisos": shares_destinos(theta, dist, log_v, g_test),
            "pivote_permisos": pivote_por_permisos(base.shares, g_test, g_fit, theta[2]),
            "radiacion": radiacion(pob17, dist),
        }
        puntajes = {k: _puntaje(evaluar(s), observado) for k, s in modelos.items()}
        puntajes["nadie_se_muda"] = _puntaje(np.zeros_like(observado) + 1e-9, observado)
        puntajes["repetir_2012_2017"] = _puntaje(net_migration(fit), observado)
        resultados[etiqueta] = {
            "lag_anios": lag_usado,
            "ventana_ajuste": f"{2012 - lag_usado}-{2012 - lag_usado + YEARS - 1}",
            "ventana_prueba": f"{2019 - lag_usado}-{2019 - lag_usado + YEARS - 1}",
            "parametros_gravedad_permisos": dict(zip(("a_viviendas", "b_distancia_km",
                                                      "g_permisos"),
                                                     (round(x, 4) for x in theta))),
            "fuera_de_muestra_2019_2024": puntajes,
        }

    salida = {
        "comando": "python -m experiments.validar_vivienda",
        "pregunta": "¿La vivienda nueva (permisos MINVU) mejora a dónde predice que se muda "
                    "la gente?",
        "metrica": "Migración neta por comuna 2019-2024, desde los orígenes de 2019, 5 pasos "
                   "anuales con la tasa de salida 2012-2017 (igual que calibrar_hogares).",
        "parametros_gravedad": dict(zip(("a_viviendas", "b_distancia_km"),
                                        (round(x, 4) for x in grav[:2]))),
        "loglik_ajuste_por_lag": {str(k): round(v["loglik"], 1) for k, v in por_lag.items()},
        "resultados": resultados,
        "llegadas_externas": prueba_reparto(codes, permisos, pob17, viv17),
        "supuestos": [
            "Solo cambian los destinos; la tasa de salida es la de 2012-2017 en todos.",
            "Permisos en ventanas de 5 años, normalizados por las viviendas del censo 2017.",
            "Un permiso no es una vivienda terminada (ver data/vivienda/README.md).",
            "2019-2024 incluye el estallido y la pandemia.",
        ],
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("gravedad:", salida["parametros_gravedad"], "| loglik por lag:",
          salida["loglik_ajuste_por_lag"])
    print(json.dumps(salida["llegadas_externas"], ensure_ascii=False, indent=1))
    for etiqueta, r in resultados.items():
        print(f"\n== {etiqueta} (lag {r['lag_anios']}; ajuste {r['ventana_ajuste']}, prueba "
              f"{r['ventana_prueba']}) {r['parametros_gravedad_permisos']}")
        for k, p in r["fuera_de_muestra_2019_2024"].items():
            print(f"  {k:24s} RMSE {p['rmse_personas']:>8,.0f}  MAE {p['mae_personas']:>7,.0f}"
                  f"  corr {p['correlacion']}")


if __name__ == "__main__":
    main()
