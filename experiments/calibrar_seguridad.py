"""Fit and test the crime inertia model (log-rate AR(1) per commune and group).

Context §6: "Seguridad: dejar comunas completas fuera del ajuste", compare against "todo sigue
igual" and "sigue la tendencia", and count how many real values fall inside the 80 % band.

- Atypical years 2019 (social unrest), 2020 and 2021 (pandemic) are left out of the commune
  means and of the year pairs that estimate phi and sigma (context §4).
- Leave-commune-out: for each commune, phi and sigma are fitted on the other 51 communes with
  the pairs 2017->2018 and 2022->2023; the commune's own mean uses its 2017, 2018, 2022 and
  2023 rates. Then 2024 is predicted one step ahead (from 2023) and two steps ahead (from 2022).
- Alternatives: persistence ("todo sigue igual"), the 2022->2023 trend extended one more year
  ("sigue la tendencia") and the pre-pandemic mean (2017-2018).
- Metric: RMSE of the log ratio predicted/observed (about the relative error) on the DMCS
  total rate, and coverage of the 80 % band per commune and group.

The parameters for the simulation are then fitted on all 52 communes with every valid pair
(2017->2018, 2022->2023, 2023->2024).

Usage:  python -m experiments.calibrar_seguridad
Output: results/seguridad_calibracion.json
"""
from __future__ import annotations

import json

import numpy as np
from scipy import special

from core.seguridad import GROUPS
from experiments.datos_aire import ROOT, load_communes
from experiments.datos_seguridad import YEARS, load_rates

OUTPUT = ROOT / "results" / "seguridad_calibracion.json"
ATYPICAL = (2019, 2020, 2021)
Z80 = float(special.ndtri(0.9))


def year(y: int) -> int:
    return YEARS.index(y)


def fit_ar(logs: np.ndarray, means: np.ndarray, pairs) -> tuple[np.ndarray, np.ndarray]:
    """phi, sigma per group by least squares through the origin on deviations from the mean."""
    phi, sigma = np.empty(len(GROUPS)), np.empty(len(GROUPS))
    for g in range(len(GROUPS)):
        x = np.concatenate([logs[year(a), :, g] - means[:, g] for a, _ in pairs])
        y = np.concatenate([logs[year(b), :, g] - means[:, g] for _, b in pairs])
        phi[g] = float(x @ y / (x @ x))
        sigma[g] = float(np.sqrt(np.mean((y - phi[g] * x) ** 2)))
    return phi, sigma


def rmse(x) -> float:
    return round(float(np.sqrt(np.mean(np.square(x)))), 4)


def main() -> None:
    communes = load_communes()
    rates = load_rates(communes.codes)
    logs = np.log(rates)
    n = len(communes.codes)
    test_years = [2017, 2018, 2022, 2023]
    means_test = logs[[year(y) for y in test_years]].mean(axis=0)  # (n, groups)
    test_pairs = [(2017, 2018), (2022, 2023)]

    pred1, pred2, inside1, inside2 = [], [], [], []
    for c in range(n):
        others = np.arange(n) != c
        phi, sigma = fit_ar(logs[:, others], means_test[others], test_pairs)
        mu = means_test[c]
        one = mu + phi * (logs[year(2023), c] - mu)
        two = mu + phi ** 2 * (logs[year(2022), c] - mu)
        observed = logs[year(2024), c]
        inside1.append(np.abs(observed - one) <= Z80 * sigma)
        inside2.append(np.abs(observed - two) <= Z80 * sigma * np.sqrt(1 + phi ** 2))
        pred1.append(np.exp(one).sum())
        pred2.append(np.exp(two).sum())

    total = rates.sum(axis=2)
    observed = np.log(total[year(2024)])
    alternatives = {
        "modelo_1_anio": np.log(pred1),
        "modelo_2_anios": np.log(pred2),
        "persistencia_2023": np.log(total[year(2023)]),
        "persistencia_2022": np.log(total[year(2022)]),
        "tendencia_2022_2023": np.log(total[year(2023)] ** 2 / total[year(2022)]),
        "media_prepandemia_2017_2018": np.log(total[[year(2017), year(2018)]].mean(axis=0)),
    }

    valid = [y for y in YEARS if y not in ATYPICAL]
    means_all = logs[[year(y) for y in valid]].mean(axis=0)
    phi, sigma = fit_ar(logs, means_all, [(2017, 2018), (2022, 2023), (2023, 2024)])

    result = {
        "comando": "python -m experiments.calibrar_seguridad",
        "variable": "Delitos de mayor connotación social (DMCS) por 100.000 habitantes, CEAD",
        "grupos": {"property": "robos con fuerza, robo de vehículo y hurtos",
                   "violent": "homicidios, lesiones, violaciones, robos con violencia o por "
                              "sorpresa y violencia intrafamiliar"},
        "anios_atipicos_excluidos": list(ATYPICAL),
        "prueba_2024": {
            "metrica": "RMSE del logaritmo de predicho/observado en la tasa DMCS total "
                       "(aprox. error relativo); comunas completas fuera del ajuste",
            **{k: rmse(v - observed) for k, v in alternatives.items()},
            "cobertura_banda_80_1_anio": round(float(np.mean(inside1)), 3),
            "cobertura_banda_80_2_anios": round(float(np.mean(inside2)), 3),
        },
        "parametros": {
            "phi": dict(zip(GROUPS, map(float, phi), strict=True)),
            "sigma": dict(zip(GROUPS, map(float, sigma), strict=True)),
            "anios_media": valid,
            "media_log_por_comuna": {
                code: dict(zip(GROUPS, map(float, means_all[i]), strict=True))
                for i, code in enumerate(communes.codes)},
            "tasa_2024_por_comuna": {
                code: dict(zip(GROUPS, map(float, rates[year(2024), i]), strict=True))
                for i, code in enumerate(communes.codes)},
        },
        "datos": ["data/seguridad/delitos_comuna_anio.csv"],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"prueba_2024": result["prueba_2024"],
                      "phi": result["parametros"]["phi"],
                      "sigma": result["parametros"]["sigma"]}, ensure_ascii=False, indent=1))
    print(f"\n{OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
