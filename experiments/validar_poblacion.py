"""Does opening the household model project population per comuna better?

Out-of-sample test: start from the Censo 2017 population, project 7 years to 2024 with rates
estimated only from 2012-2017 data, and compare per comuna with the Censo 2024.

Models compared (same start, same horizon):
- `sin_cambio`: population stays as in 2017.
- `cerrado`: internal moves only (core.hogares.MigrationModel, the model in production).
- `abierto`: internal moves plus births, deaths, arrivals from other regions and abroad,
  and departures to other regions.
- `ine_crecimiento`: the official INE projection (base 2017) growth per comuna, applied to the
  census 2017 population. `ine_nivel` is the INE level as published; it corrects census
  omission, so it is not on the same scale as the census count.

Diagnostic, not a prediction: `abierto_vitales_observados` replaces the birth and death rates
with the births and deaths that actually happened in 2017-2023. It uses test-period data, so it
only shows how much of the open model's error comes from natural growth.

Rates (annual, per resident, fixed per comuna):
- births and deaths: mean of 2012-2016 (data/vitales/) over the 2017 population;
- external flows: Censo 2017 five-year counts (data/censo/flujos_externos.csv) / 5 over the
  2017 population.

Usage:  python -m experiments.validar_poblacion   -> results/poblacion_validacion.json
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass

import numpy as np

from core.hogares import MigrationModel
from experiments.datos_aire import ROOT, load_communes
from experiments.datos_hogares import load_moves, load_population_dwellings

ANIOS = 7  # April 2017 -> April 2024
AJUSTE_VITALES = range(2012, 2017)
SALIDA = ROOT / "results" / "poblacion_validacion.json"


@dataclass(frozen=True)
class TasasAbiertas:
    """Annual rates per resident and per comuna."""

    natalidad: np.ndarray
    mortalidad: np.ndarray
    llegan_regiones: np.ndarray
    llegan_extranjero: np.ndarray
    salen_regiones: np.ndarray

    def neto(self) -> np.ndarray:
        return (self.natalidad - self.mortalidad + self.llegan_regiones
                + self.llegan_extranjero - self.salen_regiones)


def proyectar(modelo: MigrationModel, poblacion: np.ndarray, tasas: TasasAbiertas,
              anios: int) -> np.ndarray:
    """(anios + 1, n) populations: each year internal moves, then the open-system balance."""
    poblacion = np.asarray(poblacion, dtype=float)
    neto = tasas.neto()
    if neto.shape != poblacion.shape:
        raise ValueError(f"rates must have shape {poblacion.shape}, got {neto.shape}")
    filas = [poblacion]
    for _ in range(anios):
        movida, _ = modelo.step(filas[-1])
        filas.append(np.maximum(movida + filas[-1] * neto, 0.0))
    return np.array(filas)


def proyectar_con_vitales(modelo: MigrationModel, poblacion: np.ndarray, tasas: TasasAbiertas,
                          vitales: np.ndarray) -> np.ndarray:
    """Like `proyectar`, but natural growth is the given absolute counts per year.

    `vitales` has shape (anios, n): births minus deaths of each simulated year.
    """
    externo = tasas.llegan_regiones + tasas.llegan_extranjero - tasas.salen_regiones
    filas = [np.asarray(poblacion, dtype=float)]
    for neto_natural in vitales:
        movida, _ = modelo.step(filas[-1])
        filas.append(np.maximum(movida + filas[-1] * externo + neto_natural, 0.0))
    return np.array(filas)


def _leer(ruta) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def tasas_2012_2017(codes: tuple[str, ...], pob2017: np.ndarray) -> TasasAbiertas:
    vit = _leer(ROOT / "data" / "vitales" / "nacimientos_defunciones.csv")
    ext = {r["codigo"]: r for r in _leer(ROOT / "data" / "censo" / "flujos_externos.csv")
           if r["periodo"] == "2012-2017"}

    def media(col: str) -> np.ndarray:
        suma = {c: 0.0 for c in codes}
        for r in vit:
            if int(r["anio"]) in AJUSTE_VITALES:
                suma[r["codigo"]] += float(r[col])
        return np.array([suma[c] for c in codes]) / len(AJUSTE_VITALES)

    def anual(col: str) -> np.ndarray:
        return np.array([float(ext[c][col]) for c in codes]) / 5.0

    return TasasAbiertas(
        natalidad=media("nacimientos") / pob2017,
        mortalidad=media("defunciones") / pob2017,
        llegan_regiones=anual("llegan_otras_regiones") / pob2017,
        llegan_extranjero=anual("llegan_extranjero") / pob2017,
        salen_regiones=anual("salen_a_otras_regiones") / pob2017,
    )


def _errores(pred: np.ndarray, real: np.ndarray, inicio: np.ndarray) -> dict:
    err = pred - real
    return {
        "rmse_personas": round(float(np.sqrt(np.mean(err ** 2))), 1),
        "error_absoluto_medio_personas": round(float(np.mean(np.abs(err))), 1),
        "error_porcentual_medio": round(float(np.mean(np.abs(err) / real)) * 100, 2),
        "total_rm_predicho": round(float(pred.sum())),
        "correlacion_crecimiento": round(float(np.corrcoef(pred - inicio, real - inicio)[0, 1]), 3)
        if np.std(pred - inicio) > 0 else None,
    }


def main() -> None:
    codes = load_communes().codes
    pob17, _ = load_population_dwellings(codes, 2017)
    pob24, _ = load_population_dwellings(codes, 2024)
    modelo = MigrationModel.from_census(load_moves(codes, "2012-2017"))
    tasas = tasas_2012_2017(codes, pob17)

    cerrado, _ = modelo.run(pob17, ANIOS)
    abierto = proyectar(modelo, pob17, tasas, ANIOS)
    proy = {(r["codigo"], int(r["anio"])): float(r["poblacion"])
            for r in _leer(ROOT / "data" / "censo" / "proyeccion_ine.csv")}
    ine17 = np.array([proy[(c, 2017)] for c in codes])
    ine24 = np.array([proy[(c, 2024)] for c in codes])
    modelos = {"sin_cambio": pob17, "cerrado": cerrado[-1], "abierto": abierto[-1],
               "ine_crecimiento": pob17 * ine24 / ine17, "ine_nivel": ine24}
    errores = {k: _errores(v, pob24, pob17) for k, v in modelos.items()}

    vit = _leer(ROOT / "data" / "vitales" / "nacimientos_defunciones.csv")
    neto = {(r["codigo"], int(r["anio"])): float(r["nacimientos"]) - float(r["defunciones"])
            for r in vit}
    observados = np.array([[neto[(c, a)] for c in codes] for a in range(2017, 2017 + ANIOS)])
    diag = proyectar_con_vitales(modelo, pob17, tasas, observados)[-1]
    diagnostico = {"abierto_vitales_observados": _errores(diag, pob24, pob17),
                   "aviso": "Usa nacimientos y defunciones 2017-2023 (período de prueba). "
                            "No es una predicción: separa el error de la natalidad del resto."}

    err_abierto = abierto[-1] - pob24
    orden = np.argsort(-np.abs(err_abierto))[:5]
    nombres = {r["codigo"]: r["comuna"] for r in
               _leer(ROOT / "data" / "censo" / "poblacion_viviendas.csv")}
    rm = {k: round(float(getattr(tasas, k) @ pob17)) for k in TasasAbiertas.__annotations__}
    resultado = {
        "comando": "python -m experiments.validar_poblacion",
        "pregunta": "¿Abrir el modelo de hogares mejora la proyección de población por comuna?",
        "prueba": "Población 2017 (censo) proyectada 7 años con tasas de 2012-2017; "
                  "comparada con el censo 2024 por comuna.",
        "real": {"total_rm_2017": round(float(pob17.sum())), "total_rm_2024": round(float(
            pob24.sum()))},
        "errores": errores,
        "diagnostico": diagnostico,
        "flujos_anuales_rm_ajuste": rm,
        "mayores_errores_abierto": [
            {"codigo": codes[i], "comuna": nombres[codes[i]],
             "predicho": round(float(abierto[-1][i])), "real": round(float(pob24[i]))}
            for i in orden],
        "supuestos": [
            "Tasas fijas por comuna, estimadas solo con 2012-2017; denominador: población 2017.",
            "Nacimientos y defunciones: media 2012-2016 de los anuarios del INE.",
            "Flujos externos: conteos quinquenales del censo 2017 divididos por 5.",
            "Las salidas al extranjero no se miden (el censo solo cuenta residentes en Chile).",
            "residencia_ignorada no se asigna a ningún flujo.",
        ],
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(f"Real RM: 2017 {pob17.sum():,.0f} -> 2024 {pob24.sum():,.0f}")
    for k, e in errores.items():
        print(f"{k:11s} RMSE {e['rmse_personas']:>9,.0f}  MAE {e['error_absoluto_medio_personas']:>9,.0f}"
              f"  MAPE {e['error_porcentual_medio']:5.2f}%  total {e['total_rm_predicho']:>10,}"
              f"  corr crec {e['correlacion_crecimiento']}")
    e = diagnostico["abierto_vitales_observados"]
    print(f"DIAG vitales observados: RMSE {e['rmse_personas']:,.0f}  total "
          f"{e['total_rm_predicho']:,}  corr crec {e['correlacion_crecimiento']}")
    print("Flujos anuales RM (ajuste):", rm)
    print("Mayores errores (abierto):", resultado["mayores_errores_abierto"])


if __name__ == "__main__":
    main()
