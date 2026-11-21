"""Fit the household migration model on 2012->2017 and test it on 2019->2024.

- Fit: annual out-rates and destination shares from the 2012->2017 census matrix.
- In-sample check: 5 annual steps from the 2012 origin populations must reproduce the 2017
  destinations (annualising a 5-year question is not exact; this measures how much it costs).
- Out-of-sample test: 5 annual steps from the 2019 origin populations with the 2012->2017
  parameters, against the observed 2019->2024 net migration per commune. Alternatives:
  nobody moves, and the 2012->2017 net migration repeated as is.

2019->2024 includes the 2019 social unrest and the pandemic: part of the error can come from
that period, not from the model.

Usage:  python -m experiments.calibrar_hogares
Output: results/hogares_calibracion.json
"""
from __future__ import annotations

import json

import numpy as np

from core.hogares import MigrationModel, net_migration
from experiments.datos_aire import ROOT, load_communes
from experiments.datos_hogares import load_moves

OUTPUT = ROOT / "results" / "hogares_calibracion.json"
YEARS = 5


def rmse(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def score(predicted: np.ndarray, observed: np.ndarray) -> dict:
    return {
        "rmse_personas": round(rmse(predicted - observed), 1),
        "mae_personas": round(float(np.mean(np.abs(predicted - observed))), 1),
        "correlacion": round(float(np.corrcoef(predicted, observed)[0, 1]), 3)
        if np.std(predicted) > 0 else None,
    }


def main() -> None:
    communes = load_communes()
    fit = load_moves(communes.codes, "2012-2017")
    test = load_moves(communes.codes, "2019-2024")
    model = MigrationModel.from_census(fit, years=YEARS)

    # In-sample: from the 2012 origins, 5 annual steps.
    pops, _ = model.run(fit.sum(axis=1), YEARS)
    in_sample = score(pops[-1] - pops[0], net_migration(fit))

    # Out-of-sample: 2019 origins, 2012->2017 parameters.
    pops_test, _ = model.run(test.sum(axis=1), YEARS)
    predicted = pops_test[-1] - pops_test[0]
    observed = net_migration(test)
    repeat = net_migration(fit)
    test_rate = MigrationModel.from_census(test, years=YEARS).out_rate

    errors = predicted - observed
    worst = np.argsort(-np.abs(errors))[:5]
    result = {
        "comando": "python -m experiments.calibrar_hogares",
        "modelo": "Tasa de salida anual (riesgo constante) + destinos con las proporciones "
                  "observadas 2012-2017 (core/hogares.py)",
        "ajuste": "2012-2017",
        "prueba": "2019-2024",
        "en_muestra_2012_2017": in_sample,
        "fuera_de_muestra_2019_2024": {
            "modelo": score(predicted, observed),
            "nadie_se_muda": score(np.zeros_like(observed), observed),
            "repetir_2012_2017": score(repeat, observed),
            "mudanzas_observadas": round(float(test.sum() - np.trace(test))),
            "tasa_salida_anual": {
                "mediana_ajuste": round(float(np.median(model.out_rate)), 4),
                "mediana_prueba": round(float(np.median(test_rate)), 4),
                "correlacion": round(float(np.corrcoef(model.out_rate, test_rate)[0, 1]), 3),
            },
            "mayores_errores": [
                {"comuna": communes.names[i], "codigo": communes.codes[i],
                 "observado": round(float(observed[i])), "modelo": round(float(predicted[i]))}
                for i in worst
            ],
        },
        "supuestos": [
            "Tasa de salida anual constante: r = 1 - (1 - R5)^(1/5).",
            ("Destinos con las proporciones observadas en 2012-2017; el aire no cambia los "
             "destinos (no identificable con el censo)."),
            "Sistema cerrado: sin nacimientos, muertes ni mudanzas desde o hacia fuera de la RM.",
            "2019-2024 incluye el estallido y la pandemia: parte del error puede ser del período.",
        ],
        "datos": ["data/censo/mudanzas_2012_2017.csv", "data/censo/mudanzas_2019_2024.csv"],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("en_muestra_2012_2017",
                                             "fuera_de_muestra_2019_2024")},
                     ensure_ascii=False, indent=1))
    print(f"\n{OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
