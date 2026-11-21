"""Many promises with little execution vs few promises with much execution.

Both packages target wood burning (leña) in the PPDA Zona B, the main lever of the air model,
starting from 2023 emissions with no other policy, so the comparison is isolated.

- Muchas promesas: ban leña in each of the 18 Zona B communes (18 measures). Credibility is
  the observed PPDA base rate (ECOS-Chile 2023, conservative reading: 0.347).
- Pocas promesas: one measure, cut Zona B leña by f %. Credibility 0.8 is an ASSUMPTION
  (hypothetical credible executor); it is not taken from any source.

f is chosen so that a spreadsheet sees both packages as equal:
    credibility x promised reduction  ->  0.347 x 100 % = 0.8 x f   ->  f = 43.4 %.
The simulation then shows where they differ (median, worst case, chance of meeting the norm).

The "many promises" package is run with two executor structures (one regional executor or 18
municipalities), and every result is repeated with rho_theta = 0 and with a 5-year ramp, so
the conclusions are shown together with what they depend on.

Usage:  python -m experiments.promesas
Output: results/promesas.json
"""
from __future__ import annotations

import json

import numpy as np

from core.ciclo import Intervention, simulate
from core.credibilidad import DEFAULT_RHO_THETA, BetaCredibility, Measure, draw_theta
from core.estado import SOURCES
from experiments.datos_aire import ROOT
from experiments.simular import (
    CONCENTRATION,
    PM25_ANNUAL_NORM,
    READINGS,
    YEARS,
    YEARS_TO_FULL,
    Setup,
    load_setup,
)

OUTPUT_NAME = "promesas.json"
SEED = 22
REPLICAS = 2000
LOW_CREDIBILITY = READINGS["conservadora"]
HIGH_CREDIBILITY = 0.8  # assumption: hypothetical credible executor
CUT = LOW_CREDIBILITY / HIGH_CREDIBILITY  # spreadsheet-equivalent reduction for one promise

VARIANTS = {
    "muchas-promesas-un-ejecutor": "18 prohibiciones comunales a cargo de un ejecutor regional",
    "muchas-promesas-18-municipios": "18 prohibiciones comunales, cada una de su municipio",
    "pocas-promesas": f"Una medida: reducir {CUT:.0%} la leña de la Zona B, ejecutor creíble",
}
DEFAULT = {"rho_theta": DEFAULT_RHO_THETA, "years_to_full": YEARS_TO_FULL}
SENSITIVITY = {
    "credibilidad-independiente": {"rho_theta": 0.0, "years_to_full": YEARS_TO_FULL},
    "rampa-5-anios": {"rho_theta": DEFAULT_RHO_THETA, "years_to_full": 5},
}


def _credibility(mean: float) -> BetaCredibility:
    return BetaCredibility(mean * CONCENTRATION, (1 - mean) * CONCENTRATION)


def build_package(setup: Setup, variant: str, years_to_full: int) -> list[Intervention]:
    codes = setup.state.codes
    if variant == "pocas-promesas":
        measure = Measure("pocas-reduccion-zona-b", "ejecutor-creible",
                          _credibility(HIGH_CREDIBILITY), "supuesto")
        return [Intervention(measure, "heating", setup.in_b.copy(), 1.0 - CUT, years_to_full)]
    interventions = []
    for i in np.flatnonzero(setup.in_b):
        mask = np.zeros(len(codes), dtype=bool)
        mask[i] = True
        executor = ("seremi-rm" if variant == "muchas-promesas-un-ejecutor"
                    else f"municipio-{codes[i]}")
        measure = Measure(f"prohibicion-lena-{codes[i]}", executor,
                          _credibility(LOW_CREDIBILITY), "tasa_base")
        interventions.append(Intervention(measure, "heating", mask, 0.0, years_to_full))
    return interventions


def simulate_package(setup: Setup, interventions: list[Intervention], *, rho_theta: float,
                     replicas: int) -> np.ndarray:
    """(replicas, years, communes) PM2.5."""
    out = np.empty((replicas, len(YEARS), setup.state.n_communes))
    measures = [iv.measure for iv in interventions]
    for r in range(replicas):
        theta = draw_theta(measures, seed=SEED, replica=r, rho_theta=rho_theta)
        out[r] = simulate(setup.state, setup.air, interventions, theta, n_years=len(YEARS),
                          seed=SEED, replica=r)
    return out


def spreadsheet_value(setup: Setup, interventions: list[Intervention], weights: np.ndarray,
                      credibility: float) -> float:
    """What a spreadsheet predicts: current level + credibility x fully delivered effect."""
    full = setup.state.emissions.copy()
    for iv in interventions:
        full[iv.communes, SOURCES.index(iv.source)] *= iv.factor_at_full
    now = setup.air.concentration(setup.state.emissions) @ weights
    delivered = setup.air.concentration(full) @ weights
    return float(now + credibility * (delivered - now))


def summarize(pm: np.ndarray, weights: np.ndarray, population: np.ndarray) -> dict:
    regional = pm @ weights  # (replicas, years)
    final = regional[:, -1]
    exposed = (pm[:, -1, :] > PM25_ANNUAL_NORM) @ population
    p10, p50, p90 = np.quantile(final, [0.1, 0.5, 0.9])
    return {
        "media": round(float(final.mean()), 3),
        "p10": round(float(p10), 3),
        "p50": round(float(p50), 3),
        "p90": round(float(p90), 3),
        "ancho_banda": round(float(p90 - p10), 3),
        "prob_bajo_norma_2036": round(float(np.mean(final < PM25_ANNUAL_NORM)), 3),
        "personas_sobre_norma_p50": int(np.median(exposed)),
        "trayectoria_regional": {
            k: [round(float(v), 3) for v in row]
            for k, row in zip(("p10", "p50", "p90"),
                              np.quantile(regional, [0.1, 0.5, 0.9], axis=0), strict=True)
        },
        "prob_bajo_norma_por_anio": [
            round(float(v), 3) for v in np.mean(regional < PM25_ANNUAL_NORM, axis=0)],
    }


def run_comparison(setup: Setup, replicas: int = REPLICAS) -> dict:
    population = setup.state.population
    weights = population / population.sum()
    credibility = {"muchas-promesas-un-ejecutor": LOW_CREDIBILITY,
                   "muchas-promesas-18-municipios": LOW_CREDIBILITY,
                   "pocas-promesas": HIGH_CREDIBILITY}

    def block(settings: dict) -> dict:
        rows = {}
        for variant in VARIANTS:
            package = build_package(setup, variant, settings["years_to_full"])
            pm = simulate_package(setup, package, rho_theta=settings["rho_theta"],
                                  replicas=replicas)
            rows[variant] = {
                "planilla": round(spreadsheet_value(setup, package, weights,
                                                    credibility[variant]), 3),
                **summarize(pm, weights, population),
            }
        return {"supuestos": settings, "variantes": rows}

    return {
        "comando": "python -m experiments.promesas",
        "pregunta": "¿Da lo mismo prometer mucho y cumplir poco que prometer poco y cumplirlo?",
        "replicas": replicas,
        "semilla": SEED,
        "anios": YEARS,
        "norma_ugm3": PM25_ANNUAL_NORM,
        "nivel_2023_ugm3": round(float(setup.state.pm25 @ weights), 3),
        "variantes": VARIANTS,
        "credibilidad": {
            "baja": {"media": round(LOW_CREDIBILITY, 3),
                     "origen": "ECOS-Chile 2023, lectura conservadora (tasa base del PPDA)"},
            "alta": {"media": HIGH_CREDIBILITY,
                     "origen": "Supuesto: ejecutor creíble hipotético; no viene de una fuente"},
        },
        "reduccion_pocas_promesas": round(CUT, 4),
        "empate_en_planilla": "credibilidad x reducción prometida es igual en ambos paquetes",
        "principal": block(DEFAULT),
        "sensibilidad": {name: block(settings) for name, settings in SENSITIVITY.items()},
    }


def main() -> None:
    setup = load_setup()
    result = run_comparison(setup)
    output = ROOT / "results" / OUTPUT_NAME
    output.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Nivel 2023: {result['nivel_2023_ugm3']} µg/m³ · norma {PM25_ANNUAL_NORM}")
    for title, data in [("principal", result["principal"]),
                        *result["sensibilidad"].items()]:
        print(f"\n[{title}] {data['supuestos']}")
        print(f"{'variante':<32} planilla  media   p10    p50    p90  ancho  P(<norma)")
        for name, row in data["variantes"].items():
            print(f"{name:<32} {row['planilla']:7.2f} {row['media']:6.2f} {row['p10']:6.2f} "
                  f"{row['p50']:6.2f} {row['p90']:6.2f} {row['ancho_banda']:5.2f} "
                  f"{row['prob_bajo_norma_2036']:8.2f}")
    print(f"\n{output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
