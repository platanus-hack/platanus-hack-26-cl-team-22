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
from core.seguridad import GROUPS, CrimeModel, EffectSize, SecurityIntervention, simulate_security
from experiments.datos_aire import ROOT, Communes, load_communes, load_emissions
from experiments.datos_hogares import load_moves, load_population_dwellings

OUTPUT = ROOT / "viz" / "datos" / "simulacion.json"
CALIBRATION = ROOT / "results" / "aire_calibracion.json"
PROMISES = ROOT / "results" / "promesas.json"
HOUSEHOLDS_CALIBRATION = ROOT / "results" / "hogares_calibracion.json"
SECURITY_CALIBRATION = ROOT / "results" / "seguridad_calibracion.json"

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

SEC_VARIABLE = "seguridad"
# Security (docs/modelo-seguridad.md). Every value below was fixed before looking at outputs.
SECURITY_COVERAGE = 0.25  # scenario choice: share of a commune's property DMCS treated
SECURITY_CREDIBILITY = BetaCredibility(0.35 * 4, 0.65 * 4)  # assumption: wide, no history
SECURITY_YEARS_TO_FULL = 10
NEIGHBOR_KM = 6.0  # assumption: centroid distance (no commune polygons in the repo)
SPILLOVER = (-0.1, 0.2)  # assumption: open sign, diffusion more likely (Bowers et al. 2011)
SECURITY_TARGETS = 5  # illustrative policies act in the 5 communes with the highest DMCS rate

ASSUMPTIONS = [
    ("Communes with a station start from their measured level: the station's 2023 residual is "
     "kept constant (measured level + modelled change); communes without a station use the "
     "model alone (docs/modelo-aire.md)."),
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
    (f"Security policies cover {SECURITY_COVERAGE:.0%} of a commune's property crime, have "
     f"municipal credibility with mean 0.35 and a wide band, and reach communes within "
     f"{NEIGHBOR_KM:.0f} km with a share drawn in [{SPILLOVER[0]}, {SPILLOVER[1]}] (open sign)."),
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


@dataclass(frozen=True)
class SecurityPolicy:
    id: str
    name: str
    effects: dict[str, EffectSize]
    citation: str
    effect: str


SECURITY_POLICIES = (
    SecurityPolicy(
        "ilustrativa-camaras", "Cámaras con monitoreo activo (ilustrativa)",
        {"property": EffectSize(1.161, 1.023, 1.317, 0.95),
         "violent": EffectSize(1.050, 0.954, 1.155, 0.95)},
        "Piza, Welsh, Farrington y Thomas (2019), Criminology & Public Policy 18:135-159, "
        "tabla 1",
        f"Cubre el {SECURITY_COVERAGE:.0%} de los delitos contra la propiedad de cada comuna; "
        "en el área cubierta, OR 1,161 (propiedad) y 1,050 (violentos, no significativo)."),
    SecurityPolicy(
        "ilustrativa-iluminacion", "Mejor iluminación de calles (ilustrativa)",
        {"property": EffectSize(1.14, 1.03, 1.27, 0.90),
         "violent": EffectSize(0.99, 0.87, 1.13, 0.90)},
        "Welsh, Farrington y Douglas (2021), informe Brå, tabla 2 y pág. 35; Criminology & "
        "Public Policy (2022)",
        f"Cubre el {SECURITY_COVERAGE:.0%} de los delitos contra la propiedad de cada comuna; "
        "en el área cubierta, RES 1,14 (propiedad) y 0,99 (violentos, no significativo)."),
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
    for sp in SECURITY_POLICIES:
        scenarios.append({"id": f"con-{sp.id}", "nombre": f"Con: {sp.name}",
                          "politicas_activas": [*in_force, sp.id],
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
    measured: np.ndarray  # communes whose level is anchored to a station


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
    anchoring = calibration["anchoring"]["communes"]
    offset = np.array([anchoring[c]["residuo_ugm3"] if c in anchoring else 0.0
                       for c in communes.codes])
    measured = np.array([c in anchoring for c in communes.codes])
    air = AirModel(transfer, params["background_ugm3"],
                   np.array([params["coefficients_by_source"][s] for s in SOURCES]), offset)
    state = RegionState(BASE_YEAR, communes.codes, air.concentration(emissions),
                        communes.population_2024, emissions)
    for i, code in enumerate(communes.codes):
        if code in anchoring and abs(state.pm25[i] - anchoring[code]["medido_ugm3"]) > 0.01:
            raise SystemExit(f"Anchored commune {code} does not start at its measured level: "
                             f"rerun python -m experiments.calibrar_aire")
    return Setup(communes, in_b, masks, air, state, calibration, measured)


def featured_communes(setup: Setup) -> list[str]:
    """Few communes with contrast (team review): the two highest and two lowest measured
    levels, plus every Zona B commune with a station. Only measured communes qualify."""
    measured = np.flatnonzero(setup.measured)
    order = measured[np.argsort(-setup.state.pm25[measured])]
    chosen = [*order[:2], *order[-2:], *[i for i in measured if setup.in_b[i]]]
    return [setup.communes.codes[i] for i in dict.fromkeys(int(i) for i in chosen)]


def population_housing_validation() -> dict:
    """Validation blocks for population (open model) and new housing, if their results exist.

    Read from results/poblacion_validacion.json and results/vivienda_validacion.json, written by
    experiments/validar_poblacion.py and experiments/validar_vivienda.py.
    """
    blocks: dict = {}
    pop_file = ROOT / "results" / "poblacion_validacion.json"
    if pop_file.exists():
        pop = json.loads(pop_file.read_text(encoding="utf-8"))
        err = pop["errores"]
        blocks["poblacion"] = {
            "fuente": "results/poblacion_validacion.json",
            "comando": pop["comando"],
            "metrica": "Población por comuna en 2024, proyectada desde el censo 2017 con tasas "
                       "de 2012-2017",
            "unidad": "personas",
            "rmse_modelo": err["abierto"]["rmse_personas"],
            "rmse_sin_cambio": err["sin_cambio"]["rmse_personas"],
            "rmse_cerrado": err["cerrado"]["rmse_personas"],
            "rmse_proyeccion_ine": err["ine_crecimiento"]["rmse_personas"],
            "total_rm_modelo": err["abierto"]["total_rm_predicho"],
            "total_rm_real": pop["real"]["total_rm_2024"],
            "aviso": "Nadie le gana a «sin cambio» en 7 años, tampoco el INE: los nacimientos "
                     "cayeron 31 % y las salidas a otras regiones subieron.",
        }
    housing_file = ROOT / "results" / "vivienda_validacion.json"
    if housing_file.exists():
        housing = json.loads(housing_file.read_text(encoding="utf-8"))
        res = housing["resultados"]["lag_elegido_en_ajuste"]["fuera_de_muestra_2019_2024"]
        blocks["vivienda"] = {
            "fuente": "results/vivienda_validacion.json",
            "comando": housing["comando"],
            "metrica": "Migración neta por comuna 2019-2024 según a dónde van quienes se mudan",
            "unidad": "personas",
            "rmse_modelo": res["proporciones_2012_2017"]["rmse_personas"],
            "rmse_pivote_permisos": res["pivote_permisos"]["rmse_personas"],
            "rmse_gravedad_permisos": res["gravedad_permisos"]["rmse_personas"],
            "rmse_radiacion": res["radiacion"]["rmse_personas"],
            "aviso": "La vivienda nueva central la ocuparon llegadas desde el extranjero: los "
                     "permisos no mejoran los destinos de las mudanzas internas.",
        }
    return blocks


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
    security_fit = json.loads(SECURITY_CALIBRATION.read_text(encoding="utf-8"))
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

    # --- Security: crime model and illustrative policies (docs/modelo-seguridad.md) ---
    sp_params = security_fit["parametros"]
    log_mean = np.array([[sp_params["media_log_por_comuna"][c][g] for g in GROUPS]
                         for c in communes.codes])
    phi = np.array([sp_params["phi"][g] for g in GROUPS])
    near = distance_matrix_km(communes.lat, communes.lon) < NEIGHBOR_KM
    np.fill_diagonal(near, False)
    crime = CrimeModel(communes.codes, log_mean, phi,
                       np.array([sp_params["sigma"][g] for g in GROUPS]), near)
    rate_2024 = np.array([[sp_params["tasa_2024_por_comuna"][c][g] for g in GROUPS]
                          for c in communes.codes])
    # 2025 is not simulated with noise: the first simulated year (2026) starts from the
    # expected 2025 level, one AR step from 2024.
    log_start = log_mean + phi * (np.log(rate_2024) - log_mean)
    targets = np.argsort(-rate_2024.sum(axis=1))[:SECURITY_TARGETS]
    target_codes = [communes.codes[i] for i in targets]
    sec_by_id = {sp.id: sp for sp in SECURITY_POLICIES}

    def security_interventions(policy: SecurityPolicy) -> list[SecurityIntervention]:
        out = []
        for i in targets:
            mask = np.zeros(n, dtype=bool)
            mask[i] = True
            code = communes.codes[i]
            measure = Measure(f"{policy.id}-{code}", f"municipio-{code}", SECURITY_CREDIBILITY,
                              "supuesto")
            out.append(SecurityIntervention(measure, mask, SECURITY_COVERAGE, policy.effects,
                                            SECURITY_YEARS_TO_FULL))
        return out

    sec_cache: dict[frozenset[str], np.ndarray] = {}

    def run_security(active: list[str]) -> np.ndarray:
        """(replicas, years, communes) DMCS rate; same keyed streams for every scenario."""
        key = frozenset(pid for pid in active if pid in sec_by_id)
        if key not in sec_cache:
            ivs = [iv for pid in sorted(key) for iv in security_interventions(sec_by_id[pid])]
            measures = [iv.measure for iv in ivs]
            out = np.empty((REPLICAS, len(YEARS), n))
            for r in range(REPLICAS):
                theta = draw_theta(measures, seed=SEED, replica=r)
                out[r] = simulate_security(crime, log_start, ivs, theta, n_years=len(YEARS),
                                           seed=SEED, replica=r, spillover=SPILLOVER).sum(axis=2)
            sec_cache[key] = out
        return sec_cache[key]

    def run(active: list[str], reading: str, households: str) -> np.ndarray:
        """(replicas, years, communes) PM2.5, same seed and keyed streams for every scenario."""
        active = [pid for pid in active if pid in by_id]
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
        sec = run_security(sc["politicas_activas"])
        trajectories[sc["id"]] = {
            code: {VARIABLE: bands(pm[:, :, i]),
                   # deterministic: no band (policies and air do not move people)
                   POP_VARIABLE: {k: growth_bands[code] for k in ("p10", "p50", "p90")},
                   SEC_VARIABLE: bands(sec[:, :, i])}
            for i, code in enumerate(communes.codes)}
        exposed = np.einsum("rtc,tc->rt", pm > PM25_ANNUAL_NORM, population)
        impact[sc["id"]] = {k: [round(v) for v in vals] for k, vals in bands(exposed).items()}
        contributions[sc["id"]] = {code: {VARIABLE: [], POP_VARIABLE: [], SEC_VARIABLE: []}
                                   for code in communes.codes}
        for pid in sc["politicas_activas"]:
            rest = [q for q in sc["politicas_activas"] if q != pid]
            if pid in sec_by_id:
                variable, now, without = SEC_VARIABLE, sec, run_security(rest)
            else:
                variable, now = VARIABLE, pm
                without = run(rest, sc["lectura"], sc["hogares"])
            delta = np.median(now[:, -1, :] - without[:, -1, :], axis=0)
            for i, code in enumerate(communes.codes):
                contributions[sc["id"]][code][variable].append(
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
            "seguridad": "DMCS por 100.000 habitantes (CEAD), con inercia por comuna. Las "
                         "políticas de seguridad son ilustrativas (todavía no hay planes "
                         "comunales clasificados): actúan en las 5 comunas de mayor tasa 2024 y "
                         "solo reducen delitos contra la propiedad (docs/modelo-seguridad.md).",
            "aviso": "El modelo de aire responde cuánto mejora la región, no qué comunas ganan "
                     "más: su patrón espacial no le gana a «el mismo cambio en todas». Las "
                     "diferencias de nivel entre comunas solo son medidas donde hay estación.",
            "nivel_base": "medido: nivel anclado a la estación de la comuna (modelo + residuo "
                          "2023); modelado: comunas sin estación, solo el modelo. Los cambios "
                          "por política son modelados en ambos casos.",
            "comunas_destacadas": "Regla fija: las dos de mayor y las dos de menor nivel "
                                  "medido, más las de la Zona B con estación.",
            "supuestos": ASSUMPTIONS,
        },
        "variables": [
            {"id": VARIABLE, "nombre": "PM2,5 media anual", "unidad": "µg/m³", "mejor": "menor"},
            {"id": POP_VARIABLE, "nombre": f"Crecimiento de la población desde {POP_START_YEAR}",
             "unidad": "%", "mejor": "mayor"},
            {"id": SEC_VARIABLE, "nombre": "Delitos de mayor connotación social (DMCS)",
             "unidad": "casos por 100.000 habitantes", "mejor": "menor"},
        ],
        "comunas": [
            {"codigo": code, "nombre": name, "lat": float(lat), "lon": float(lon),
             "zona_ppda": "B" if b else "A", f"poblacion_{POP_START_YEAR}": int(p0),
             "nivel_base": "medido" if med else "modelado",
             "base": {VARIABLE: round(float(c), 3), POP_VARIABLE: 0.0,
                      SEC_VARIABLE: round(float(r24), 1)}}
            for code, name, lat, lon, b, c, p0, med, r24 in zip(
                communes.codes, communes.names, communes.lat, communes.lon, in_b, state.pm25,
                pop_start, setup.measured, rate_2024.sum(axis=1), strict=True)
        ],
        "comunas_destacadas": featured_communes(setup),
        "tipos_hogar": [
            {"id": "sensible-aire", "nombre": "Sensible a la contaminación",
             "pesos": {VARIABLE: 0.6, SEC_VARIABLE: 0.2, POP_VARIABLE: 0.2}},
            {"id": "prioriza-seguridad", "nombre": "Prioriza seguridad",
             "pesos": {VARIABLE: 0.2, SEC_VARIABLE: 0.6, POP_VARIABLE: 0.2}},
            {"id": "busca-crecimiento", "nombre": "Prefiere comunas que crecen",
             "pesos": {VARIABLE: 0.2, SEC_VARIABLE: 0.2, POP_VARIABLE: 0.6}},
            {"id": "equilibrado", "nombre": "Equilibrado",
             "pesos": {VARIABLE: 0.34, SEC_VARIABLE: 0.33, POP_VARIABLE: 0.33}},
        ],
        "politicas": [
            {"id": p.id, "nombre": p.name, "nivel": "regional",
             "tipo": "vigente" if p.in_force else "propuesta",
             "fuente": SOURCE_LABEL[p.source],
             "comunas": "todas" if p.zone == "todas" else
             [c for c, m in zip(communes.codes, masks[p.zone], strict=True) if m],
             "credibilidad": {k: round(v, 3) for k, v in credibility_summary(p).items()},
             "procedencia": "tasa_base", "cita": p.citation, "efecto": p.effect,
             "variable": VARIABLE}
            for p in POLICIES
        ] + [
            {"id": sp.id, "nombre": sp.name, "nivel": "comunal", "tipo": "ilustrativa",
             "fuente": "seguridad", "comunas": target_codes,
             "credibilidad": {k: round(v, 3) for k, v in SECURITY_CREDIBILITY.summary().items()},
             "procedencia": "supuesto", "cita": sp.citation, "efecto": sp.effect,
             "variable": SEC_VARIABLE}
            for sp in SECURITY_POLICIES
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
            "seguridad": {
                "fuente": "results/seguridad_calibracion.json",
                "comando": security_fit["comando"],
                "metrica": security_fit["prueba_2024"]["metrica"],
                **{k: v for k, v in security_fit["prueba_2024"].items() if k != "metrica"},
                "aviso": "Los efectos de las intervenciones no se validan localmente: no hay "
                         "datos de cámaras ni de iluminación por comuna.",
            },
            "hogares": {
                "fuente": "results/hogares_calibracion.json",
                "comando": households_fit["comando"],
                "metrica": "Migración neta por comuna 2019-2024 (ajuste con 2012-2017)",
                "rmse_modelo": oos["modelo"]["rmse_personas"],
                "rmse_nadie_se_muda": oos["nadie_se_muda"]["rmse_personas"],
                "rmse_repetir_2012_2017": oos["repetir_2012_2017"]["rmse_personas"],
                "correlacion_modelo": oos["modelo"]["correlacion"],
                "unidad": "personas",
                "aviso": "2019-2024 incluye el estallido y la pandemia.",
            },
            **population_housing_validation(),
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
    print(f"\nDMCS 2036 en las {SECURITY_TARGETS} comunas intervenidas "
          f"({', '.join(communes.names[i] for i in targets)}), media de p10/p50/p90:")
    for sc in scenarios:
        final = run_security(sc["politicas_activas"])[:, -1, targets].mean(axis=1)
        p10, p50, p90 = np.quantile(final, [0.1, 0.5, 0.9])
        print(f"{sc['id']:<48} {p10:7.0f} {p50:7.0f} {p90:7.0f}")
    print(f"DMCS 2024 en esas comunas: {rate_2024[targets].sum(axis=1).mean():.0f}")
    print(f"Base {BASE_YEAR}: {state.pm25 @ (pop_start / pop_start.sum()):.2f} µg/m³ | "
          f"{OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
