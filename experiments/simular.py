"""Run the simulation and write the real viz/datos/simulacion.json.

Inputs:  data/ (communes, RETC emissions, census moves), results/aire_calibracion.json (air
         parameters), results/promesas.json, results/hogares_calibracion.json.
Model:   core/ciclo.py (credibility -> emissions -> coupled air) with households moving between
         communes (core/hogares.py) and, in one reading, carrying residential heating with them.
Contract: docs/plan-comunas.md. Credibility: docs/credibilidad.md. Air: docs/modelo-aire.md.
Households: docs/modelo-hogares.md.

Usage:  python -m experiments.simular
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass

import numpy as np

from core.aire import AirModel, distance_matrix_km, exponential_transfer
from core.ciclo import Intervention, simulate
from core.credibilidad import (
    DEFAULT_RHO,
    DEFAULT_RHO_THETA,
    BetaCredibility,
    Measure,
    draw_theta,
)
from core.estado import SOURCES, RegionState
from core.hogares import MigrationModel
from experiments.datos_aire import ROOT, Communes, load_communes, load_emissions
from experiments.datos_hogares import load_moves, load_population_dwellings

OUTPUT = ROOT / "viz" / "datos" / "simulacion.json"
CALIBRATION = ROOT / "results" / "aire_calibracion.json"
PROMISES = ROOT / "results" / "promesas.json"
HOUSEHOLDS_CALIBRATION = ROOT / "results" / "hogares_calibracion.json"

SEED = 22
REPLICAS = 500
BASE_YEAR = 2023
YEARS = list(range(2026, 2037))
YEARS_TO_FULL = 10  # assumption: the PPDA sets a 10-year horizon (art. 1)
PM25_ANNUAL_NORM = 20.0  # ug/m3, Chilean annual PM2.5 standard (docs/politicas-aire.md)
EXECUTOR = "ppda-rm"
VARIABLE = "pm25_anual"
POP_VARIABLE = "crecimiento_poblacion"
POP_START_YEAR = 2024  # census population the households mechanism starts from
HOUSEHOLD_FIT = "2012-2017"  # validated parameters (docs/modelo-hogares.md)
TOP_FLOWS = 15
# Does residential heating follow the people who move? (docs/modelo-hogares.md)
HOUSEHOLD_READINGS = {
    "fija": "La leña de cada comuna no cambia con su población: cota inferior, sin acople.",
    "proporcional": "La leña de cada comuna crece o baja con su población: cota superior.",
}
DEFAULT_HOUSEHOLDS = "fija"

# PPDA art. 73: Zona B = these 18 communes; Zona A = the other 34.
ZONA_B = ("Alhué", "Buin", "Calera de Tango", "Colina", "Curacaví", "El Monte", "Isla de Maipo",
          "Lampa", "María Pinto", "Melipilla", "Padre Hurtado", "Paine", "Peñaflor", "Pirque",
          "San Pedro", "San José de Maipo", "Talagante", "Tiltil")

# ECOS-Chile (2023) review of 157 PPDA measures: 38 conforming, 33 partial, 86 without public
# evidence. Partial counts as half (assumption).
CONFORMING, PARTIAL, NO_EVIDENCE = 38, 33, 86
FULFILLED = CONFORMING + 0.5 * PARTIAL
READINGS = {
    "conservadora": FULFILLED / (CONFORMING + PARTIAL + NO_EVIDENCE),  # no evidence = not done
    "optimista": FULFILLED / (CONFORMING + PARTIAL),  # no evidence excluded from the count
}
CONCENTRATION = 10.0  # assumption: Beta alpha + beta, sets the width of each measure's band
DEFAULT_READING = "conservadora"

ASSUMPTIONS = [
    ("Emissions start at the 2023 RETC values (industry 2023, avoiding the 2024 Las Condes "
     "jump) and stay constant until 2026 and for every source no policy targets."),
    (f"Each executed year delivers 1/{YEARS_TO_FULL} of a measure's full effect (PPDA 10-year "
     "horizon, art. 1)."),
    "Turning off a policy in force means no further progress from the 2023 level, not a rebound.",
    ("Credibility of every PPDA measure comes from the ECOS-Chile (2023) base rate; partial "
     "measures count as half; the Beta concentration (10) is an assumption."),
    (f"Measures of the same executor fail together in the same year (rho = {DEFAULT_RHO}) and "
     f"share part of their credibility (rho_theta = {DEFAULT_RHO_THETA}); both are one-factor "
     "copulas."),
    ("The -30 % for large establishments (arts. 57-58) is applied to all declared industry: an "
     "upper bound."),
    ("Households move every year with the 2012-2017 census out-rates and destination shares, "
     "starting from the 2024 census; the region is closed (no births, deaths or moves from "
     "outside), so its total is constant. Air does not change destinations."),
    ("Housing capacity grows at each commune's 2017-2024 dwelling growth rate; it never binds "
     "in 2025-2036."),
    ("Residential heating either stays fixed or follows population (two readings); transport, "
     "industry and other sources do not follow residents."),
]


def _key(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name)
    return "".join(c for c in plain if not unicodedata.combining(c)).lower().strip()


@dataclass(frozen=True)
class Policy:
    id: str
    name: str
    source: str
    zone: str  # "A", "B" or "todas"
    factor_at_full: float
    in_force: bool
    citation: str
    effect: str


POLICIES = (
    Policy("ppda-lena-zona-a", "Prohibición de calefactores a leña en la Zona A", "heating", "A",
           0.0, True, "PPDA RM, D.S. 31/2016, art. 74",
           "Las emisiones de leña de las 34 comunas de la Zona A bajan hasta 0."),
    Policy("ppda-industria-30", "Grandes establecimientos bajan 30 % su emisión de MP",
           "industry", "todas", 0.7, True, "PPDA RM, D.S. 31/2016, arts. 57-58",
           "Las emisiones industriales bajan 30 % (cota superior: el plan solo lo exige a los "
           "grandes establecimientos)."),
    Policy("propuesta-lena-zona-b", "Extender la prohibición de leña a la Zona B (propuesta)",
           "heating", "B", 0.0, False, "Propuesta; hoy la Zona B solo restringe calefactores "
           "nuevos (PPDA art. 75)",
           "Las emisiones de leña de las 18 comunas de la Zona B bajan hasta 0."),
)
SOURCE_LABEL = {"heating": "lena", "transport": "transporte", "industry": "industria",
                "other": "otras"}


def build_scenarios() -> list[dict]:
    """Toggle scenarios (conservative reading, fixed heating) plus labelled variants."""
    in_force = [p.id for p in POLICIES if p.in_force]
    scenarios = [{"id": "base", "nombre": "Planes vigentes", "politicas_activas": in_force,
                  "lectura": DEFAULT_READING}]
    for pid in in_force:
        name = next(p.name for p in POLICIES if p.id == pid)
        scenarios.append({"id": f"sin-{pid}", "nombre": f"Sin avance: {name}",
                          "politicas_activas": [q for q in in_force if q != pid],
                          "lectura": DEFAULT_READING})
    for p in POLICIES:
        if not p.in_force:
            scenarios.append({"id": f"con-{p.id}", "nombre": f"Con: {p.name}",
                              "politicas_activas": [*in_force, p.id],
                              "lectura": DEFAULT_READING})
    scenarios.append({"id": "sin-politicas", "nombre": "Ninguna política avanza",
                      "politicas_activas": [], "lectura": DEFAULT_READING})
    scenarios.append({"id": "base-lectura-optimista",
                      "nombre": "Planes vigentes, si lo que no tiene evidencia se cumplió",
                      "politicas_activas": in_force, "lectura": "optimista"})
    scenarios.append({"id": "base-plan-escrito", "nombre": "Planes vigentes, cumplidos al 100 %",
                      "politicas_activas": in_force, "lectura": "plan-escrito"})
    proposed = [p.id for p in POLICIES if not p.in_force]
    follow = "proporcional"
    scenarios.append({"id": "sin-politicas-lena-sigue-a-la-gente",
                      "nombre": "Ninguna política avanza; la leña sigue a quienes se mudan",
                      "politicas_activas": [], "lectura": DEFAULT_READING, "hogares": follow})
    scenarios.append({"id": "base-lena-sigue-a-la-gente",
                      "nombre": "Planes vigentes; la leña sigue a quienes se mudan",
                      "politicas_activas": in_force, "lectura": DEFAULT_READING,
                      "hogares": follow})
    scenarios.append({"id": "con-propuesta-lena-zona-b-lena-sigue-a-la-gente",
                      "nombre": "Con la prohibición en la Zona B; la leña sigue a quienes se mudan",
                      "politicas_activas": [*in_force, *proposed], "lectura": DEFAULT_READING,
                      "hogares": follow})
    for sc in scenarios:
        sc.setdefault("hogares", DEFAULT_HOUSEHOLDS)
    return scenarios


@dataclass(frozen=True)
class Setup:
    communes: Communes
    in_b: np.ndarray
    masks: dict[str, np.ndarray]
    air: AirModel
    state: RegionState
    calibration: dict


def load_setup() -> Setup:
    """Communes, PPDA zones, calibrated air model and the initial state (2023 emissions)."""
    communes = load_communes()
    n = len(communes.codes)
    zona_b_keys = {_key(name) for name in ZONA_B}
    in_b = np.array([_key(name) in zona_b_keys for name in communes.names])
    if in_b.sum() != len(ZONA_B) or (~in_b).sum() != 34:
        missing = zona_b_keys - {_key(name) for name in communes.names}
        raise SystemExit(f"Zone mapping failed: {in_b.sum()} in Zona B; unmatched {missing}")
    masks = {"A": ~in_b, "B": in_b, "todas": np.ones(n, dtype=bool)}

    emissions, _ = load_emissions(communes.codes, BASE_YEAR)
    calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    params = calibration["parameters"]
    transfer = exponential_transfer(distance_matrix_km(communes.lat, communes.lon),
                                    params["scale_km"])
    air = AirModel(transfer, params["background_ugm3"],
                   np.array([params["coefficients_by_source"][s] for s in SOURCES]))
    state = RegionState(BASE_YEAR, communes.codes, air.concentration(emissions),
                        communes.population_2024, emissions)
    return Setup(communes, in_b, masks, air, state, calibration)


def main() -> None:
    setup = load_setup()
    communes, in_b, masks, air, state = (setup.communes, setup.in_b, setup.masks, setup.air,
                                         setup.state)
    calibration = setup.calibration
    if not PROMISES.exists():
        raise SystemExit(f"Missing {PROMISES.relative_to(ROOT)}: run python -m "
                         "experiments.promesas first (or make simulate)")
    promises = json.loads(PROMISES.read_text(encoding="utf-8"))
    households_fit = json.loads(HOUSEHOLDS_CALIBRATION.read_text(encoding="utf-8"))
    n = len(communes.codes)
    heating = state.emissions[:, SOURCES.index("heating")]
    print(f"Leña {BASE_YEAR}: Zona B {heating[in_b].sum():.0f} of {heating.sum():.0f} t")

    # --- Households: population path, independent of policies (air does not move people) ---
    migration = MigrationModel.from_census(load_moves(communes.codes, HOUSEHOLD_FIT))
    pop_start, dwellings_24 = load_population_dwellings(communes.codes, POP_START_YEAR)
    _, dwellings_17 = load_population_dwellings(communes.codes, 2017)
    steps = YEARS[-1] - POP_START_YEAR
    dwelling_growth = (dwellings_24 / dwellings_17) ** (1 / (POP_START_YEAR - 2017))
    capacity = np.array([pop_start * dwelling_growth ** (t + 1) for t in range(steps)])
    pops, flows = migration.run(pop_start, steps, capacity)
    binding = int(np.isclose(pops[1:], capacity, rtol=1e-9).any(axis=0).sum())
    year_index = [y - POP_START_YEAR for y in YEARS]
    population = pops[year_index]  # (years, communes)
    year_flows = flows[[i - 1 for i in year_index]]  # moves during each simulated year
    heating_scale = {"fija": None, "proporcional": population / pop_start}
    print(f"Zona B population {POP_START_YEAR}: {pop_start[in_b].sum():,.0f} -> {YEARS[-1]}: "
          f"{population[-1][in_b].sum():,.0f}; communes at housing capacity: {binding}")

    def intervention(policy: Policy, reading: str) -> Intervention:
        # "plan-escrito" overrides theta with 1, so its Beta is never sampled.
        mean = READINGS.get(reading, READINGS[DEFAULT_READING])
        credibility = BetaCredibility(mean * CONCENTRATION, (1 - mean) * CONCENTRATION)
        measure = Measure(policy.id, EXECUTOR, credibility, "tasa_base")
        return Intervention(measure, policy.source, masks[policy.zone], policy.factor_at_full,
                            YEARS_TO_FULL)

    by_id = {p.id: p for p in POLICIES}
    cache: dict[tuple[frozenset[str], str, str], np.ndarray] = {}

    def run(active: list[str], reading: str, households: str) -> np.ndarray:
        """(replicas, years, communes) PM2.5, same seed and keyed streams for every scenario."""
        key = (frozenset(active), reading, households)
        if key not in cache:
            ivs = [intervention(by_id[pid], reading) for pid in sorted(active)]
            out = np.empty((REPLICAS, len(YEARS), n))
            for r in range(REPLICAS):
                measures = [iv.measure for iv in ivs]
                theta = (np.ones(len(ivs)) if reading == "plan-escrito"
                         else draw_theta(measures, seed=SEED, replica=r))
                out[r] = simulate(state, air, ivs, theta, n_years=len(YEARS), seed=SEED,
                                  replica=r, heating_scale=heating_scale[households])
            cache[key] = out
        return cache[key]

    def bands(x: np.ndarray) -> dict[str, list[float]]:
        q = np.quantile(x, [0.1, 0.5, 0.9], axis=0)
        return {k: [round(float(v), 3) for v in row] for k, row in zip(("p10", "p50", "p90"), q,
                                                                        strict=True)}

    growth_pct = (population / pop_start - 1.0) * 100.0
    growth_bands = {code: [round(float(v), 3) for v in growth_pct[:, i]]
                    for i, code in enumerate(communes.codes)}

    scenarios = build_scenarios()
    trajectories, contributions, impact = {}, {}, {}
    for sc in scenarios:
        pm = run(sc["politicas_activas"], sc["lectura"], sc["hogares"])
        trajectories[sc["id"]] = {
            code: {VARIABLE: bands(pm[:, :, i]),
                   # deterministic: no band (policies and air do not move people)
                   POP_VARIABLE: {k: growth_bands[code] for k in ("p10", "p50", "p90")}}
            for i, code in enumerate(communes.codes)}
        exposed = np.einsum("rtc,tc->rt", pm > PM25_ANNUAL_NORM, population)
        impact[sc["id"]] = {k: [round(v) for v in vals] for k, vals in bands(exposed).items()}
        contributions[sc["id"]] = {code: {VARIABLE: [], POP_VARIABLE: []}
                                   for code in communes.codes}
        for pid in sc["politicas_activas"]:
            without = run([q for q in sc["politicas_activas"] if q != pid], sc["lectura"],
                          sc["hogares"])
            delta = np.median(pm[:, -1, :] - without[:, -1, :], axis=0)
            for i, code in enumerate(communes.codes):
                contributions[sc["id"]][code][VARIABLE].append(
                    {"politica_id": pid, "delta_p50_final": round(float(delta[i]), 3)})

    def credibility_summary(policy: Policy) -> dict:
        return intervention(policy, DEFAULT_READING).measure.credibility.summary()

    fit, test24, change = (calibration["fit"], calibration["test_2024_levels"],
                           calibration["test_change_2017_2023"])
    top_flows = []
    for y, f in zip(YEARS, year_flows, strict=True):
        order = np.argsort(f, axis=None)[::-1][:TOP_FLOWS]
        for flat in order:
            o, d = divmod(int(flat), n)
            top_flows.append({"anio": y, "origen": communes.codes[o],
                              "destino": communes.codes[d], "personas": round(float(f[o, d]))})
    net = year_flows.sum(axis=1) - year_flows.sum(axis=2)  # (years, communes)
    oos = households_fit["fuera_de_muestra_2019_2024"]
    output = {
        "meta": {
            "version": "1.0",
            "es_ejemplo": False,
            "semilla": SEED,
            "replicas": REPLICAS,
            "anio_base": BASE_YEAR,
            "anios": YEARS,
            "modelo": "Aire v0: núcleo exponencial isotrópico (docs/modelo-aire.md); "
                      "hogares: tasas y destinos del censo 2012-2017 (docs/modelo-hogares.md)",
            "comando": "make simulate",
            "lectura_por_defecto": DEFAULT_READING,
            "lecturas": {
                "conservadora": "Lo que no tiene evidencia pública cuenta como no cumplido.",
                "optimista": "Lo que no tiene evidencia pública se excluye del conteo.",
                "plan-escrito": "Todas las medidas se cumplen (credibilidad 1).",
            },
            "significado_sin": "Apagar una política vigente significa que no avanza más desde "
                               "el nivel de 2023; no que la leña vuelva.",
            "aportes": "delta_p50_final: mediana, entre réplicas pareadas (misma semilla), de "
                       "PM2,5 con la política menos sin ella en el último año. Negativo = mejora.",
            "flujos": f"Personas (no hogares: el censo cuenta personas) que se mudan entre "
                      f"comunas en cada año; las {TOP_FLOWS} mayores por año. Iguales en todos "
                      "los escenarios: las políticas y el aire no cambian a dónde se muda la "
                      "gente.",
            "hogares_por_defecto": DEFAULT_HOUSEHOLDS,
            "lecturas_hogares": HOUSEHOLD_READINGS,
            "poblacion_sin_banda": "crecimiento_poblacion no tiene banda (p10 = p50 = p90): "
                                   "las mudanzas son flujos esperados, no se sortean.",
            "aviso": "El modelo v0 responde cuánto mejora la región, no qué comunas ganan más: "
                     "su patrón espacial no le gana a «el mismo cambio en todas».",
            "supuestos": ASSUMPTIONS,
        },
        "variables": [
            {"id": VARIABLE, "nombre": "PM2,5 media anual", "unidad": "µg/m³", "mejor": "menor"},
            {"id": POP_VARIABLE, "nombre": f"Crecimiento de la población desde {POP_START_YEAR}",
             "unidad": "%", "mejor": "mayor"},
        ],
        "comunas": [
            {"codigo": code, "nombre": name, "lat": float(lat), "lon": float(lon),
             "zona_ppda": "B" if b else "A", f"poblacion_{POP_START_YEAR}": int(p0),
             "base": {VARIABLE: round(float(c), 3), POP_VARIABLE: 0.0}}
            for code, name, lat, lon, b, c, p0 in zip(
                communes.codes, communes.names, communes.lat, communes.lon, in_b, state.pm25,
                pop_start, strict=True)
        ],
        "tipos_hogar": [
            {"id": "sensible-aire", "nombre": "Sensible a la contaminación",
             "pesos": {VARIABLE: 0.8, POP_VARIABLE: 0.2}},
            {"id": "busca-crecimiento", "nombre": "Prefiere comunas que crecen",
             "pesos": {VARIABLE: 0.2, POP_VARIABLE: 0.8}},
            {"id": "equilibrado", "nombre": "Equilibrado",
             "pesos": {VARIABLE: 0.5, POP_VARIABLE: 0.5}},
        ],
        "politicas": [
            {"id": p.id, "nombre": p.name, "nivel": "regional",
             "tipo": "vigente" if p.in_force else "propuesta",
             "fuente": SOURCE_LABEL[p.source],
             "comunas": "todas" if p.zone == "todas" else
             [c for c, m in zip(communes.codes, masks[p.zone], strict=True) if m],
             "credibilidad": {k: round(v, 3) for k, v in credibility_summary(p).items()},
             "procedencia": "tasa_base", "cita": p.citation, "efecto": p.effect}
            for p in POLICIES
        ],
        "escenarios": scenarios,
        "trayectorias": trajectories,
        "aportes": contributions,
        "impacto": {
            "metrica": "Personas que viven en comunas sobre la norma anual de PM2,5",
            "norma_ugm3": PM25_ANNUAL_NORM,
            "poblacion": "Población simulada de cada año (censo 2024 más mudanzas)",
            "por_escenario": impact,
        },
        "validacion": {
            "fuente": "results/aire_calibracion.json",
            "comando": calibration["command"],
            "cambio_2017_2023": {
                "observado_media": round(change["observed_mean"], 2),
                "modelo_media": round(change["predicted_mean"], 2),
                "rmse_modelo": round(change["rmse_model"], 2),
                "rmse_sin_cambio": round(change["rmse_no_change"], 2),
                "rmse_mismo_cambio_en_todas": round(change["rmse_same_change_everywhere"], 2),
            },
            "niveles_2024": {
                "rmse_modelo": round(test24["rmse_model"], 2),
                "rmse_persistencia": round(test24["rmse_persistence_2023"], 2),
                "rmse_media_otras_estaciones": round(test24["rmse_mean_of_other_stations"], 2),
            },
            "ajuste_2023": {"estaciones": fit["stations"], "r2": round(fit["r2"], 2)},
            "hogares": {
                "fuente": "results/hogares_calibracion.json",
                "comando": households_fit["comando"],
                "metrica": "Migración neta por comuna 2019-2024 (ajuste con 2012-2017)",
                "rmse_modelo": oos["modelo"]["rmse_personas"],
                "rmse_nadie_se_muda": oos["nadie_se_muda"]["rmse_personas"],
                "rmse_repetir_2012_2017": oos["repetir_2012_2017"]["rmse_personas"],
                "correlacion_modelo": oos["modelo"]["correlacion"],
                "aviso": "2019-2024 incluye el estallido y la pandemia.",
            },
        },
        # Separate comparison, not a toggle scenario: see docs/promesas.md.
        "promesas": {"fuente": f"results/{PROMISES.name}", **promises},
        "flujos": {sc["id"]: top_flows for sc in scenarios},
        "migracion_neta": {
            "unidad": "personas por año (llegan menos salen)",
            "por_comuna": {code: [round(float(v)) for v in net[:, i]]
                           for i, code in enumerate(communes.codes)},
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    weights = population[-1] / population[-1].sum()
    print(f"{'escenario':<48} PM2,5 2036 (pond. población) p10/p50/p90 | sobre norma p50")
    for sc in scenarios:
        final = run(sc["politicas_activas"], sc["lectura"], sc["hogares"])[:, -1, :] @ weights
        p10, p50, p90 = np.quantile(final, [0.1, 0.5, 0.9])
        print(f"{sc['id']:<48} {p10:6.2f} {p50:6.2f} {p90:6.2f} | "
              f"{impact[sc['id']]['p50'][-1]:>9,}")
    print(f"Base {BASE_YEAR}: {state.pm25 @ (pop_start / pop_start.sum()):.2f} µg/m³ | "
          f"{OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
