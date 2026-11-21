"""Out-of-sample validation of every mechanism against simple alternatives, in one command.

Question for each variable: does the model predict data it never saw better than
"nothing changes" (persistence) and "the trend continues"? And do its 80 % bands contain
about 80 % of the real values? Where the model loses, the report says so.

Protocol (fixed before looking at the results; constants below):

- Air: hindcast of the simulation engine itself (core/ciclo.py), not of the emissions inventory.
  2017 emissions x the PPDA measures in force (from 2018, the plan took effect on 24-nov-2017),
  executed each year according to their credibility, through the calibrated air model. Each
  station's prediction is its measured 2019 level plus the change the engine simulates for its
  commune from 2019 to the test year. Fit years 2017-2019, test years 2022-2024; 2020 and 2021
  (pandemic) are neither fitted nor scored. The air kernel (scale, background, k) is refitted
  on 2017 stations with the method of calibrar_aire.py: the simulation's own kernel is fitted
  on 2023, a test year, so it is reported only as a superseded reading.
  * "Same change everywhere": every station gets the engine's mean change over the scored
    stations. If it ties the per-station engine, the spatial pattern is not validated.
  * Persistence: the 2019 level. Trend: least-squares line over 2017-2019, extended.
  * Engine band: execution uncertainty only. The wider band adds the engine's residual error
    on the fit years (one-year changes 2017->2018 and 2018->2019 minus the engine's change:
    weather plus whatever the engine does not model), never estimated on the test years.
  * Credibility leak: the PPDA compliance review used for credibility is from 2023, inside the
    test period. The report shows theta = 0 (nothing executed) and theta = 1 (plan as written)
    next to it so the effect of that choice is visible.
- Households, population and security: read from their own calibration scripts, which already
  fit on one period and test on another (see the commands in the report).

Usage:  python -m experiments.validar   (or `make validate`, which reruns the calibrations first)
Output: results/validacion.json, docs/validacion.md and the table in README.md (between markers).
Never writes viz/datos/simulacion.json.
"""
from __future__ import annotations

import csv
import json
import unicodedata
from collections.abc import Mapping

import numpy as np

from core.aire import AirModel, distance_matrix_km, exponential_transfer
from core.ciclo import Intervention, simulate
from core.credibilidad import BetaCredibility, Measure, draw_theta
from core.estado import SOURCES, RegionState
from experiments.calibrar_aire import MODELLED, SCALES_KM, fit, loo_errors
from experiments.datos_aire import F_ANUAL, F_ESTACIONES, ROOT, load_emissions, load_stations
from experiments.simular import (
    CONCENTRATION,
    EXECUTOR,
    POLICIES,
    READINGS,
    SEED,
    YEARS_TO_FULL,
    load_setup,
)

# --- Pre-registered protocol ---
AIR_TRAIN_YEARS = (2017, 2018, 2019)
AIR_ORIGIN = 2019
AIR_TEST_YEARS = (2022, 2023, 2024)
AIR_ATYPICAL_YEARS = (2020, 2021)
AIR_SIM_START = 2017  # initial emissions; the first year with PPDA execution is 2018
AIR_KERNEL_FIT_YEAR = 2017  # the air kernel is refitted on this year for the hindcast
AIR_READING = "conservadora"
REPLICAS = 500
TIE_TOLERANCE = 0.02  # errors within 2 % of each other count as a tie
Z80 = 0.8

HOUSEHOLDS = ROOT / "results" / "hogares_calibracion.json"
SECURITY = ROOT / "results" / "seguridad_calibracion.json"
POPULATION = ROOT / "results" / "poblacion_validacion.json"
OUTPUT = ROOT / "results" / "validacion.json"
DOC = ROOT / "docs" / "validacion.md"
README = ROOT / "README.md"
MARK_START = "<!-- validacion:inicio (generado por make validate) -->"
MARK_END = "<!-- validacion:fin -->"


# --- Metrics ---
def rmse(errors: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(errors))))


def coverage(observed: np.ndarray, low: np.ndarray, high: np.ndarray) -> float:
    """Share of observed values inside [low, high], edges included."""
    return float(np.mean((observed >= low) & (observed <= high)))


def linear_trend(years: np.ndarray, values: np.ndarray, target: int) -> float:
    """Least-squares line through (years, values), evaluated at `target`."""
    slope, intercept = np.polyfit(np.asarray(years, float), np.asarray(values, float), 1)
    return float(intercept + slope * target)


def winner(errors: Mapping[str, float | None]) -> str:
    """Name of the lowest error, or "empate" when the best two are within TIE_TOLERANCE."""
    valid = sorted((e, name) for name, e in errors.items() if e is not None)
    if len(valid) > 1 and valid[1][0] - valid[0][0] <= TIE_TOLERANCE * valid[0][0]:
        return "empate"
    return valid[0][1]


# --- Air hindcast ---
def _plain(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower().strip()


def _station_series() -> tuple[dict[tuple[str, int], float], dict[str, str]]:
    """Annual means per (station, year) and the commune name of each station."""
    with F_ANUAL.open(encoding="utf-8-sig", newline="") as fh:
        series = {(r["estacion_id"], int(r["anio"])): float(r["pm25_media"])
                  for r in csv.DictReader(fh) if r["pm25_media"]}
    with F_ESTACIONES.open(encoding="utf-8-sig", newline="") as fh:
        commune = {r["estacion_id"]: r["comuna"] for r in csv.DictReader(fh)}
    return series, commune


def fit_kernel(setup, emissions: np.ndarray, year: int) -> tuple[AirModel, dict]:
    """Air kernel fitted on `year` stations, same method as calibrar_aire.py (LOO scale, NNLS)."""
    st = load_stations(year)
    communes = setup.communes
    total = emissions[:, MODELLED].sum(axis=1)

    def signal(scale_km: float) -> np.ndarray:
        d = distance_matrix_km(st.lat, st.lon, communes.lat, communes.lon)
        return exponential_transfer(d, scale_km) @ total

    by_scale = {L: rmse(loo_errors(signal(L), st.pm25)) for L in SCALES_KM}
    scale = min(by_scale, key=by_scale.get)
    background, k = fit(signal(scale), st.pm25)
    transfer = exponential_transfer(distance_matrix_km(communes.lat, communes.lon), scale)
    air = AirModel(transfer, background, np.where(MODELLED, k, 0.0), None)
    return air, {"anio": year, "estaciones": len(st.ids), "escala_km": scale,
                 "fondo_ugm3": round(background, 3), "k_ugm3_por_t": k,
                 "escala_en_el_borde": scale == max(SCALES_KM)}


def _emissions_2017(setup) -> np.ndarray:
    codes = setup.communes.codes
    emissions, _ = load_emissions(codes, AIR_SIM_START)
    transport = SOURCES.index("transport")
    # Transport exists only for 2023 in the RETC; calibrar_aire.py makes the same choice.
    emissions[:, transport] = load_emissions(codes, 2023)[0][:, transport]
    return emissions


def _engine(setup, air: AirModel, theta_mode: str, replicas: int) -> np.ndarray:
    """(replicas, years 2017..2024, communes) PM2.5 from 2017 emissions and the PPDA in force."""
    codes = setup.communes.codes
    emissions = _emissions_2017(setup)
    initial = RegionState(AIR_SIM_START, codes, air.concentration(emissions),
                                    setup.communes.population_2017, emissions)
    mean = READINGS[AIR_READING]
    credibility = BetaCredibility(mean * CONCENTRATION, (1 - mean) * CONCENTRATION)
    ivs = [Intervention(Measure(p.id, EXECUTOR, credibility, "tasa_base"), p.source,
                        setup.masks[p.zone], p.factor_at_full, YEARS_TO_FULL)
           for p in POLICIES if p.in_force]
    n_years = max(AIR_TEST_YEARS) - AIR_SIM_START
    out = np.empty((replicas, n_years + 1, len(codes)))
    for r in range(replicas):
        if theta_mode == "historial":
            theta = draw_theta([iv.measure for iv in ivs], seed=SEED, replica=r)
        else:
            theta = np.full(len(ivs), {"sin-ejecucion": 0.0, "plan-escrito": 1.0}[theta_mode])
        out[r, 0] = initial.pm25
        out[r, 1:] = simulate(initial, air, ivs, theta, n_years=n_years, seed=SEED,
                              replica=r)
    return out


def air_hindcast(replicas: int = REPLICAS) -> dict:
    setup = load_setup()
    series, station_commune = _station_series()
    index_of = {_plain(name): i for i, name in enumerate(setup.communes.names)}
    stations = sorted(sid for sid in station_commune
                      if all((sid, y) in series for y in AIR_TRAIN_YEARS)
                      and any((sid, y) in series for y in AIR_TEST_YEARS))
    pairs = [(sid, y) for sid in stations for y in AIR_TEST_YEARS if (sid, y) in series]
    col = {sid: index_of[_plain(station_commune[sid])] for sid in stations}
    t = {y: y - AIR_SIM_START for y in range(AIR_SIM_START, max(AIR_TEST_YEARS) + 1)}

    def change(engine: np.ndarray, sid: str, start: int, end: int) -> np.ndarray:
        return engine[:, t[end], col[sid]] - engine[:, t[start], col[sid]]

    air, kernel = fit_kernel(setup, _emissions_2017(setup), AIR_KERNEL_FIT_YEAR)
    engines = {mode: _engine(setup, air, mode, replicas)
               for mode in ("historial", "sin-ejecucion", "plan-escrito")}
    # Superseded: the simulation's kernel, fitted on 2023 (a test year). Reported, not scored.
    engines["kernel-2023"] = _engine(setup, setup.air, "historial", replicas)
    main = engines["historial"]

    # Weather noise from the fit years only: one-year observed change minus the engine's change.
    residuals = [(series[(sid, y + 1)] - series[(sid, y)])
                 - float(np.median(change(main, sid, y, y + 1)))
                 for sid in stations for y in AIR_TRAIN_YEARS[:-1]]
    weather_sd = rmse(np.array(residuals))
    noise = np.random.default_rng([SEED, 2019]).standard_normal((len(pairs), replicas))

    observed = np.array([series[p] for p in pairs])
    origin = np.array([series[(sid, AIR_ORIGIN)] for sid, _ in pairs])
    trend = np.array([linear_trend(np.array(AIR_TRAIN_YEARS),
                                   np.array([series[(sid, y)] for y in AIR_TRAIN_YEARS]), y)
                      for sid, y in pairs])
    low, high = (1 - Z80) / 2, 1 - (1 - Z80) / 2

    def reading(engine: np.ndarray) -> dict:
        draws = np.array([series[(sid, AIR_ORIGIN)] + change(engine, sid, AIR_ORIGIN, y)
                          for sid, y in pairs])
        median = np.median(draws, axis=1)
        return {"rmse_ugm3": round(rmse(median - observed), 3),
                "sesgo_ugm3": round(float(np.mean(median - observed)), 3),
                "draws": draws, "median": median}

    readings = {mode: reading(engine) for mode, engine in engines.items()}
    # Same change everywhere: each station gets the engine's mean change over the scored stations
    # of that year. Uses no observed test value.
    years = np.array([y for _, y in pairs])
    delta = readings["historial"]["median"] - origin
    uniform = origin + np.array([delta[years == y].mean() for y in years])
    readings["mismo-cambio-en-todas"] = {
        "rmse_ugm3": round(rmse(uniform - observed), 3),
        "sesgo_ugm3": round(float(np.mean(uniform - observed)), 3),
        "draws": None, "median": uniform}
    draws = readings["historial"]["draws"]
    weather = draws + weather_sd * noise
    q_engine = np.quantile(draws, [low, high], axis=1)
    q_weather = np.quantile(weather, [low, high], axis=1)
    model = {
        "rmse_ugm3": readings["historial"]["rmse_ugm3"],
        "sesgo_ugm3": readings["historial"]["sesgo_ugm3"],
        "cobertura_80": round(coverage(observed, *q_engine), 3),
        "cobertura_80_con_residuo": round(coverage(observed, *q_weather), 3),
        "ancho_banda_ugm3": round(float(np.mean(q_engine[1] - q_engine[0])), 3),
        "ancho_banda_con_residuo_ugm3": round(float(np.mean(q_weather[1] - q_weather[0])), 3),
    }
    return {
        "pregunta": "¿El motor (plan de descontaminación + credibilidad) predice el PM2,5 por "
                    "estación mejor que la persistencia y la tendencia?",
        "protocolo": {"ajuste": list(AIR_TRAIN_YEARS), "origen": AIR_ORIGIN,
                      "prueba": list(AIR_TEST_YEARS), "no_puntuados": list(AIR_ATYPICAL_YEARS),
                      "lectura_credibilidad": AIR_READING, "replicas": replicas, "semilla": SEED,
                      "kernel": kernel},
        "estaciones": stations,
        "n_pares": len(pairs),
        "modelo": model,
        "sin_cambio": {"rmse_ugm3": round(rmse(origin - observed), 3),
                       "sesgo_ugm3": round(float(np.mean(origin - observed)), 3)},
        "tendencia": {"rmse_ugm3": round(rmse(trend - observed), 3),
                      "sesgo_ugm3": round(float(np.mean(trend - observed)), 3)},
        "lecturas": {mode: {k: v for k, v in r.items() if k not in ("draws", "median")}
                     for mode, r in readings.items() if mode != "historial"},
        "residuo_ajuste_sd_ugm3": round(weather_sd, 3),
        "pares": [{"estacion": sid, "anio": y, "observado": round(float(o), 2),
                   "modelo": round(float(m), 2), "sin_cambio": round(float(p), 2),
                   "tendencia": round(float(tr), 2)}
                  for (sid, y), o, m, p, tr in zip(pairs, observed,
                                                   readings["historial"]["median"], origin,
                                                   trend, strict=True)],
        "avisos": [
            ("La credibilidad viene de la revisión de cumplimiento de 2023, dentro del período de "
             "prueba; ver las lecturas sin-ejecucion y plan-escrito."),
            ("Acertar la baja no prueba que la causa sea el plan: el motor no tiene renovación "
             "del parque vehicular ni clima, que también bajan el PM2,5."),
            "La tendencia usa tres puntos (2017-2019): es frágil.",
            ("Transporte 2017 usa el inventario 2023 (el RETC no lo trae antes); ninguna medida "
             "vigente lo toca, así que no mueve el cambio simulado."),
            f"{len(stations)} estaciones: no alcanza para afirmar significancia estadística.",
            *([("La escala del kernel quedó en el borde de la grilla (toda la cuenca como una "
               "caja): el acople entre comunas es casi uniforme.")]
              if kernel["escala_en_el_borde"] else []),
        ],
    }


# --- One table for every variable ---
def _row(variable: str, prueba: str, metrica: str, modelo: float, sin_cambio: float | None,
         tendencia: float | None, cobertura: float | None, n: str, fuente: str,
         notas: str = "") -> dict:
    return {"variable": variable, "prueba": prueba, "metrica": metrica, "modelo": modelo,
            "sin_cambio": sin_cambio, "tendencia": tendencia, "cobertura_80": cobertura, "n": n,
            "gana": winner({"modelo": modelo, "sin_cambio": sin_cambio, "tendencia": tendencia}),
            "fuente": fuente, "notas": notas}


def collect(air: dict) -> list[dict]:
    households = json.loads(HOUSEHOLDS.read_text(encoding="utf-8"))
    security = json.loads(SECURITY.read_text(encoding="utf-8"))
    population = json.loads(POPULATION.read_text(encoding="utf-8"))
    hh = households["fuera_de_muestra_2019_2024"]
    sec = security["prueba_2024"]
    pop = population["errores"]
    m = air["modelo"]
    return [
        _row("Aire", f"PM2,5 por estación {AIR_TEST_YEARS[0]}-{AIR_TEST_YEARS[-1]} desde "
             f"{AIR_ORIGIN} (ajuste {AIR_TRAIN_YEARS[0]}-{AIR_TRAIN_YEARS[-1]})",
             "RMSE µg/m³", m["rmse_ugm3"], air["sin_cambio"]["rmse_ugm3"],
             air["tendencia"]["rmse_ugm3"], m["cobertura_80_con_residuo"],
             f"{air['n_pares']} pares, {len(air['estaciones'])} estaciones",
             "python -m experiments.validar",
             f"Banda del motor sola: {m['cobertura_80']:.0%}. El mismo cambio en todas las "
             f"estaciones: {air['lecturas']['mismo-cambio-en-todas']['rmse_ugm3']:.2f}."),
        _row("Hogares", f"Migración neta por comuna {households['prueba']} "
             f"(ajuste {households['ajuste']})", "RMSE personas",
             hh["modelo"]["rmse_personas"], hh["nadie_se_muda"]["rmse_personas"],
             hh["repetir_2012_2017"]["rmse_personas"], None, "52 comunas",
             households["comando"], "Modelo determinista: sin banda."),
        _row("Población", "Población por comuna 2024 desde 2017 (tasas 2012-2017)",
             "RMSE personas", pop["cerrado"]["rmse_personas"], pop["sin_cambio"]["rmse_personas"],
             None, None, "52 comunas", population["comando"],
             f"Proyección oficial del INE: {pop['ine_crecimiento']['rmse_personas']:,.0f} "
             "(no es una tendencia de los años de ajuste). Sistema cerrado: no suma nacimientos "
             "ni llegadas."),
        _row("Seguridad", "Tasa de delitos 2024 a 1 año (comunas fuera del ajuste)",
             "RMSE log (≈ error relativo)", sec["modelo_1_anio"], sec["persistencia_2023"],
             sec["tendencia_2022_2023"], sec["cobertura_banda_80_1_anio"], "52 comunas",
             security["comando"], "A un año, la tasa cambia poco y repetirla es difícil de batir."),
        _row("Seguridad", "Tasa de delitos 2024 a 2 años (comunas fuera del ajuste)",
             "RMSE log (≈ error relativo)", sec["modelo_2_anios"], sec["persistencia_2022"], None,
             sec["cobertura_banda_80_2_anios"], "52 comunas", security["comando"],
             "Sin tendencia comparable: la de 2022-2023 usa un año que el modelo no ve."),
    ]


def _fmt(value: float | None, metric: str) -> str:
    if value is None:
        return "—"
    if "personas" in metric:
        return f"{value:,.0f}".replace(",", ".")
    return f"{value:.3f}".replace(".", ",") if value < 1 else f"{value:.2f}".replace(".", ",")


WINNER_LABEL = {"modelo": "**Modelo**", "sin_cambio": "Sin cambio", "tendencia": "Tendencia",
                "empate": "Empate"}


def table(rows: list[dict]) -> str:
    lines = [("| Variable | Prueba fuera de muestra | Métrica | Modelo | Sin cambio | Tendencia "
              "| Cobertura banda 80 % | Gana |"),
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        cov = "—" if r["cobertura_80"] is None else f"{r['cobertura_80']:.0%}"
        lines.append(f"| {r['variable']} | {r['prueba']} | {r['metrica']} | "
                     f"{_fmt(r['modelo'], r['metrica'])} | {_fmt(r['sin_cambio'], r['metrica'])} | "
                     f"{_fmt(r['tendencia'], r['metrica'])} | {cov} | {WINNER_LABEL[r['gana']]} |")
    return "\n".join(lines)


def document(rows: list[dict], air: dict) -> str:
    m, readings = air["modelo"], air["lecturas"]
    kernel = air["protocolo"]["kernel"]
    pattern = winner({"modelo": m["rmse_ugm3"],
                      "uniforme": readings["mismo-cambio-en-todas"]["rmse_ugm3"]})
    spatial = ("El patrón entre comunas aporta: el cambio por estación le gana a repartir el "
               "mismo cambio en todas." if pattern == "modelo" else
               "**El patrón entre comunas no está validado**: repartir el mismo cambio en todas "
               "las estaciones predice igual o mejor. El motor acierta la magnitud regional; qué "
               "comunas ganan más sale del supuesto de acople, no de la prueba.")
    notes = "\n".join(f"- **{r['variable']}** ({r['prueba']}): {r['notas']} Comando: "
                      f"`{r['fuente']}`." for r in rows)
    return f"""# Validación fuera de muestra

> Generado por `make validate` (`python -m experiments.validar`). No editar a mano.

Cada variable se ajusta con un período y se prueba con otro que el modelo no vio. Se compara
contra dos alternativas simples: **sin cambio** (el último valor conocido se repite) y
**tendencia** (sigue la línea de los años de ajuste). Gana el error más bajo; si los dos mejores
están a menos de {TIE_TOLERANCE:.0%}, es empate. Una banda del 80 % es honesta si contiene cerca
del 80 % de los valores reales.

{table(rows)}

## Notas por prueba

{notes}

## Aire: el motor de la simulación contra la realidad

Parte de las emisiones de {AIR_SIM_START}, ejecuta las medidas vigentes del plan de
descontaminación desde 2018 según su credibilidad (lectura {air['protocolo']['lectura_credibilidad']}),
y suma el cambio simulado entre {AIR_ORIGIN} y cada año de prueba al nivel medido de cada
estación en {AIR_ORIGIN}. 2020 y 2021 (pandemia) no se ajustan ni se puntúan. El kernel de aire
se reajusta con las estaciones de {kernel['anio']} (escala {kernel['escala_km']:.0f} km, mismo
método que `calibrar_aire.py`).

**Corrección del protocolo.** La primera versión usaba el kernel de la simulación, que está
ajustado con 2023, un año de prueba. Se reemplazó por el de {kernel['anio']} después de ver ese
primer resultado; el reemplazado queda abajo como referencia, no como resultado.

| Lectura | RMSE (µg/m³) | Sesgo (µg/m³) |
|---|---|---|
| Ninguna medida se ejecuta (θ = 0) | {_fmt(readings['sin-ejecucion']['rmse_ugm3'], '')} | {_fmt(readings['sin-ejecucion']['sesgo_ugm3'], '')} |
| **Historial de cumplimiento (la que usa la simulación)** | {_fmt(m['rmse_ugm3'], '')} | {_fmt(m['sesgo_ugm3'], '')} |
| Plan tal como está escrito (θ = 1) | {_fmt(readings['plan-escrito']['rmse_ugm3'], '')} | {_fmt(readings['plan-escrito']['sesgo_ugm3'], '')} |
| El mismo cambio del motor en todas las estaciones | {_fmt(readings['mismo-cambio-en-todas']['rmse_ugm3'], '')} | {_fmt(readings['mismo-cambio-en-todas']['sesgo_ugm3'], '')} |
| Reemplazado: kernel ajustado con 2023 | {_fmt(readings['kernel-2023']['rmse_ugm3'], '')} | {_fmt(readings['kernel-2023']['sesgo_ugm3'], '')} |

- Con θ = 0 el motor no agrega cambio y coincide con «sin cambio»: toda la ventaja del modelo
  viene de las medidas del plan.
- {spatial}
- Sesgo positivo = el modelo predice más contaminación de la que hubo. La lectura usada en la
  simulación no se cambia por este resultado: elegirla mirando los años de prueba sería ajustar
  con la prueba.
- Banda del motor sola: {m['cobertura_80']:.0%} de cobertura (ancho medio
  {_fmt(m['ancho_banda_ugm3'], '')} µg/m³). Solo contiene la incertidumbre de ejecución.
  Sumando el error residual del motor en los años de ajuste ({_fmt(air['residuo_ajuste_sd_ugm3'], '')} µg/m³:
  clima y lo que el motor no modela), cubre {m['cobertura_80_con_residuo']:.0%}.

Avisos:

{chr(10).join('- ' + a for a in air['avisos'])}
"""


def _replace_readme(rows: list[dict]) -> None:
    text = README.read_text(encoding="utf-8")
    if MARK_START not in text or MARK_END not in text:
        raise SystemExit(f"README.md needs the markers {MARK_START!r} and {MARK_END!r}")
    head, rest = text.split(MARK_START, 1)
    _, tail = rest.split(MARK_END, 1)
    README.write_text(f"{head}{MARK_START}\n{table(rows)}\n{MARK_END}{tail}", encoding="utf-8")


def main() -> None:
    air = air_hindcast()
    rows = collect(air)
    report = {"comando": "make validate", "protocolo_empate": TIE_TOLERANCE, "filas": rows,
              "aire": air}
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(document(rows, air), encoding="utf-8")
    _replace_readme(rows)
    print(table(rows))
    print(f"\n-> {OUTPUT.relative_to(ROOT)}, {DOC.relative_to(ROOT)}, README.md")


if __name__ == "__main__":
    main()
