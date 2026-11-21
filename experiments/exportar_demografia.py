"""Export the parameters of the open household model for the in-browser lab.

The browser engine (viz/src/lib/demografia.ts) reruns this model live while the user moves the
sliders. It must reproduce Python: the file carries reference projections computed here with
experiments.validar_poblacion.proyectar, and viz tests compare against them.

Parameters (start: census 2024 population, horizon 2036):
- internal moves: annual out-rate and destination shares from the 2012-2017 census matrix, the
  ones validated in experiments/calibrar_hogares.py and used by experiments/simular.py;
- births: mean of 2022-2023; deaths: mean of 2019, 2022 and 2023 (the 2020-2021 COVID excess is
  left out); per resident of 2024 (data/vitales/);
- external flows: census 2019-2024 five-year counts / 5, per resident of 2024
  (data/censo/flujos_externos.csv);
- INE official projection 2024-2035 per comuna, for comparison only (another scale: it corrects
  census omission; data/censo/README.md).
- agent simulation (docs/modelo-mudanzas-abm.md): capacity = census 2024 dwellings × persons per
  occupied dwelling; yearly housing permits = mean 2015-2024 (MINVU); foreign-born stock ≈
  foreign-born of 2017 + arrivals from abroad 2019-2024; network exponent phi from
  results/redes_validacion.json.

Usage:  python -m experiments.exportar_demografia   -> viz/public/datos/demografia.json
"""

from __future__ import annotations

import csv
import json

import numpy as np

from core.hogares import MigrationModel
from experiments.datos_aire import ROOT, load_communes
from experiments.datos_hogares import load_moves, load_population_dwellings
from experiments.validar_poblacion import TasasAbiertas, proyectar

SALIDA = ROOT / "viz" / "public" / "datos" / "demografia.json"
ANIO_BASE = 2024
ANIOS = list(range(ANIO_BASE, 2037))
NACIMIENTOS = (2022, 2023)
DEFUNCIONES = (2019, 2022, 2023)


def _leer(ruta) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def tasas_recientes(codes: tuple[str, ...], pob: np.ndarray) -> TasasAbiertas:
    """Annual rates per resident of `pob` from the most recent usable years."""
    vit = _leer(ROOT / "data" / "vitales" / "nacimientos_defunciones.csv")
    ext = {r["codigo"]: r for r in _leer(ROOT / "data" / "censo" / "flujos_externos.csv")
           if r["periodo"] == "2019-2024"}

    def media(col: str, anios: tuple[int, ...]) -> np.ndarray:
        suma = {c: 0.0 for c in codes}
        for r in vit:
            if int(r["anio"]) in anios:
                suma[r["codigo"]] += float(r[col])
        return np.array([suma[c] for c in codes]) / len(anios)

    def anual(col: str) -> np.ndarray:
        return np.array([float(ext[c][col]) for c in codes]) / 5.0

    return TasasAbiertas(
        natalidad=media("nacimientos", NACIMIENTOS) / pob,
        mortalidad=media("defunciones", DEFUNCIONES) / pob,
        llegan_regiones=anual("llegan_otras_regiones") / pob,
        llegan_extranjero=anual("llegan_extranjero") / pob,
        salen_regiones=anual("salen_a_otras_regiones") / pob,
    )


PERMISOS = range(2015, 2025)


def parametros_abm(codes: tuple[str, ...], pob: np.ndarray) -> dict:
    """Capacity, permits, foreign stock and phi for the agent-based moves simulation."""
    ocup = {r["codigo"]: r for r in _leer(ROOT / "data" / "censo" / "viviendas_ocupacion_2024.csv")}
    viviendas = np.array([float(ocup[c]["viviendas"]) for c in codes])
    ocupadas = np.array([float(ocup[c]["particulares_ocupadas"]) for c in codes])
    densidad = pob / ocupadas
    permisos: dict[str, float] = {c: 0.0 for c in codes}
    for r in _leer(ROOT / "data" / "vivienda" / "permisos_vivienda.csv"):
        if int(r["anio"]) in PERMISOS:
            permisos[r["codigo"]] += float(r["viviendas"]) / len(PERMISOS)
    stock = {r["codigo"]: float(r["nacidos_extranjero_2017"])
             for r in _leer(ROOT / "data" / "censo" / "stock_extranjero.csv")}
    llegadas = {r["codigo"]: float(r["llegan_extranjero"])
                for r in _leer(ROOT / "data" / "censo" / "flujos_externos.csv")
                if r["periodo"] == "2019-2024"}
    redes = json.loads((ROOT / "results" / "redes_validacion.json").read_text(encoding="utf-8"))
    return {
        "capacidad_inicial": (viviendas * densidad).tolist(),
        "permisos_anuales": [permisos[c] for c in codes],
        "personas_por_vivienda": densidad.tolist(),
        "stock_extranjero": [stock[c] + llegadas[c] for c in codes],
        "phi": redes["phi"],
        "fuentes": ["data/censo/viviendas_ocupacion_2024.csv", "data/vivienda/permisos_vivienda.csv",
                    "data/censo/stock_extranjero.csv", "results/redes_validacion.json"],
    }


def main() -> None:
    com = load_communes()
    codes = com.codes
    pob24, _ = load_population_dwellings(codes, ANIO_BASE)
    modelo = MigrationModel.from_census(load_moves(codes, "2012-2017"), years=5)
    tasas = tasas_recientes(codes, pob24)
    cero = TasasAbiertas(*(np.zeros_like(pob24) for _ in range(5)))
    n_anios = len(ANIOS) - 1

    proy = {(r["codigo"], int(r["anio"])): float(r["poblacion"])
            for r in _leer(ROOT / "data" / "censo" / "proyeccion_ine.csv")}
    anios_ine = [a for a in ANIOS if a <= 2035]

    salida = {
        "meta": {
            "comando": "python -m experiments.exportar_demografia",
            "anio_base": ANIO_BASE,
            "anios": ANIOS,
            "modelo": "Mudanzas internas (tasa de salida y destinos del censo 2012-2017) + "
                      "nacimientos − defunciones + llegadas de otras regiones y del extranjero − "
                      "salidas a otras regiones. Igual a experiments/validar_poblacion.py.",
            "fuentes": ["data/censo/mudanzas_2012_2017.csv", "data/censo/poblacion_viviendas.csv",
                        "data/censo/flujos_externos.csv", "data/vitales/nacimientos_defunciones.csv",
                        "data/censo/proyeccion_ine.csv"],
            "supuestos": [
                (f"Nacimientos: media {NACIMIENTOS[0]}-{NACIMIENTOS[1]}; defunciones: media de "
                 f"{', '.join(map(str, DEFUNCIONES))} (sin el exceso COVID de 2020-2021)."),
                "Flujos externos: censo 2019-2024 / 5. Las salidas al extranjero no se miden.",
                "Tasas fijas por comuna, por residente de 2024; sin estructura por edad.",
                "La proyección del INE corrige la omisión censal: otra escala, solo referencia.",
            ],
            "validacion": "docs/validacion-poblacion.md",
        },
        "comunas": [{"codigo": c, "nombre": n} for c, n in zip(codes, com.names)],
        "poblacion_inicial": pob24.tolist(),
        "tasa_salida": modelo.out_rate.tolist(),
        "destinos": modelo.shares.tolist(),
        "tasas": {k: getattr(tasas, k).tolist() for k in TasasAbiertas.__annotations__},
        "ine": {"anios": anios_ine,
                "poblacion": [[round(proy[(c, a)]) for c in codes] for a in anios_ine]},
        "abm": parametros_abm(codes, pob24),
        "referencia": {
            "por_defecto": {"poblacion": proyectar(modelo, pob24, tasas, n_anios).tolist()},
            "cerrado": {"poblacion": proyectar(modelo, pob24, cero, n_anios).tolist()},
        },
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False) + "\n", encoding="utf-8")
    ref = np.array(salida["referencia"]["por_defecto"]["poblacion"])
    print(f"RM 2024 {pob24.sum():,.0f} -> 2036 {ref[-1].sum():,.0f} (abierto, tasas recientes); "
          f"INE 2035 {sum(salida['ine']['poblacion'][-1]):,}")
    print(f"{SALIDA.relative_to(ROOT)}  {SALIDA.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
