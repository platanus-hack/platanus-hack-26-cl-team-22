"""Network rule of the moves simulation: do arrivals from abroad follow those who came before?

Rule (docs/modelo-mudanzas-abm.md): an arrival from abroad picks comuna j with weight
(stock_extranjero[j] + 1)^phi, where the stock is the foreign-born population already there.

Fit and test without using test data:
- fit phi: foreign-born residents of 2017 who arrived BEFORE 2012 -> arrivals from abroad
  2012-2017 (census 2017);
- test: all foreign-born residents of 2017 -> arrivals from abroad 2019-2024 (census 2024).
Alternatives on the test: the 2012-2017 arrival geography, population 2017, and phi = 1.
Metric: RMSE per comuna of the 2019-2024 arrivals, splitting the observed RM total.

Usage:  python -m experiments.validar_redes   -> results/redes_validacion.json
"""

from __future__ import annotations

import csv
import json

import numpy as np
from scipy.optimize import minimize_scalar

from experiments.datos_aire import ROOT, load_communes
from experiments.datos_hogares import load_population_dwellings

SALIDA = ROOT / "results" / "redes_validacion.json"


def pesos_redes(stock: np.ndarray, phi: float) -> np.ndarray:
    """Destination shares (stock + 1)^phi, normalized."""
    w = (np.asarray(stock, dtype=float) + 1.0) ** phi
    return w / w.sum()


def ajustar_phi(llegadas: np.ndarray, stock: np.ndarray) -> float:
    """Maximum-likelihood phi of a multinomial split of `llegadas` with `pesos_redes`."""
    llegadas = np.asarray(llegadas, dtype=float)
    log_s = np.log(np.asarray(stock, dtype=float) + 1.0)

    def nll(phi: float) -> float:
        u = phi * log_s
        lse = u.max() + np.log(np.exp(u - u.max()).sum())
        return -float(np.sum(llegadas * (u - lse)))

    return float(minimize_scalar(nll, bounds=(0.0, 3.0), method="bounded",
                                 options={"xatol": 1e-8}).x)


def _leer(ruta) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _puntaje(pred: np.ndarray, obs: np.ndarray) -> dict:
    return {"rmse_personas": round(float(np.sqrt(np.mean((pred - obs) ** 2))), 1),
            "correlacion": round(float(np.corrcoef(pred, obs)[0, 1]), 3)}


def main() -> None:
    codes = load_communes().codes
    stock = {r["codigo"]: r for r in _leer(ROOT / "data" / "censo" / "stock_extranjero.csv")}
    ext = {(r["codigo"], r["periodo"]): r for r in
           _leer(ROOT / "data" / "censo" / "flujos_externos.csv")}
    s_antes = np.array([float(stock[c]["llegaron_antes_2012"]) for c in codes])
    s_2017 = np.array([float(stock[c]["nacidos_extranjero_2017"]) for c in codes])
    lleg_ajuste = np.array([float(ext[(c, "2012-2017")]["llegan_extranjero"]) for c in codes])
    lleg_prueba = np.array([float(ext[(c, "2019-2024")]["llegan_extranjero"]) for c in codes])
    pob17, _ = load_population_dwellings(codes, 2017)

    phi = ajustar_phi(lleg_ajuste, s_antes)
    total = lleg_prueba.sum()
    modelos = {
        "redes_phi_ajustado": pesos_redes(s_2017, phi),
        "redes_phi_1": pesos_redes(s_2017, 1.0),
        "geografia_2012_2017": lleg_ajuste / lleg_ajuste.sum(),
        "poblacion_2017": pob17 / pob17.sum(),
    }
    prueba = {k: _puntaje(total * w, lleg_prueba) for k, w in modelos.items()}
    ajuste = {"redes_phi_ajustado": _puntaje(lleg_ajuste.sum() * pesos_redes(s_antes, phi),
                                             lleg_ajuste)}
    salida = {
        "comando": "python -m experiments.validar_redes",
        "regla": "peso_j = (stock_extranjero_j + 1)^phi",
        "phi": round(phi, 4),
        "ajuste": {"datos": "stock que llegó antes de 2012 -> llegadas 2012-2017", **ajuste},
        "prueba_2019_2024": {"datos": "stock 2017 -> llegadas 2019-2024",
                             "total_rm_observado": round(float(total)), **prueba},
        "supuestos": [
            "El stock antes de 2012 se mide en la comuna de residencia de 2017 (aproximación).",
            "Solo se reparte el total observado: la prueba mide a dónde llegan, no cuántos.",
        ],
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"phi = {phi:.3f}  (ajuste corr {ajuste['redes_phi_ajustado']['correlacion']})")
    for k, p in prueba.items():
        print(f"  {k:22s} RMSE {p['rmse_personas']:>8,.0f}  corr {p['correlacion']}")


if __name__ == "__main__":
    main()
