"""Download INE census files and build the RM move matrices and comuna totals.

Usage (from the repo root):  .venv/bin/python -m datos.censo.fetch_censo
Raw files are cached in data/raw/censo/ (ignored by git); delete one to download it again.
Outputs in data/censo/:
  mudanzas_2012_2017.csv   Censo 2017, built from person microdata
  mudanzas_2019_2024.csv   Censo 2024, reshaped from the INE table D5 (sheet "2")
  poblacion_viviendas.csv  population and dwellings per comuna, both censuses
Needs pandas, openpyxl, requests and `bsdtar` (the 2017 files are nested RAR archives).
Never fills gaps: anything missing stays out and is reported in data/censo/README.md.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import openpyxl
import pandas as pd
import requests

from datos.censo.censo import COLUMNAS, completar_rm, es_comuna_rm, matriz_2024, pares_2017

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "censo"
OUT = ROOT / "data" / "censo"

INE17 = ("https://www.ine.gob.cl/docs/default-source/censo-de-poblacion-y-vivienda/bbdd/"
         "censo-2017/csv/")
CENSO24 = "https://censo2024.ine.gob.cl/wp-content/uploads/2025/"
FUENTES = {
    "D5_Migracion-interna.xlsx": CENSO24 + "04/D5_Migracion-interna.xlsx",
    "V1_Viviendas-y-hogares-censados.xlsx": CENSO24 + "03/V1_Viviendas-y-hogares-censados.xlsx",
    "Poblacion-censada-y-residentes-habituales-Censo-2017.xlsx":
        CENSO24 + "04/Poblacion-censada-y-residentes-habituales-Censo-2017.xlsx",
    "csv-personas-censo-2017.zip": INE17 + "csv-personas-censo-2017.zip",
    "csv-viviendas-censo-2017.zip": INE17 + "csv-viviendas-censo-2017.zip",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (research script; hackathon census data)"}

COLS_P17 = ["COMUNA", "P10", "P10COMUNA", "P11", "P11COMUNA"]
# Censo 2017 dwelling type P01: 1-7 private dwellings, 8 collective; 9 and 10 are
# "operativo personas en tránsito / calle" and are not dwellings.
P01_VIVIENDA = range(1, 9)


def descargar(nombre: str) -> Path:
    """Return the cached raw file, downloading it once with retries."""
    destino = RAW / nombre
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    url, ultimo = FUENTES[nombre], None
    for espera in (0, 5, 15, 45):
        time.sleep(espera)
        try:
            with requests.get(url, headers=HEADERS, timeout=120, stream=True) as r:
                if r.status_code == 200:
                    parcial = destino.with_suffix(destino.suffix + ".part")
                    with parcial.open("wb") as fh:
                        for bloque in r.iter_content(1 << 20):
                            fh.write(bloque)
                    parcial.rename(destino)
                    return destino
                ultimo = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            ultimo = repr(e)
    sys.exit(f"Could not download {url}: {ultimo}")


def hoja(nombre: str, pestana: str) -> list[tuple]:
    libro = openpyxl.load_workbook(descargar(nombre), read_only=True)
    return list(libro[pestana].iter_rows(values_only=True))


def filas_comuna(filas: list[tuple]) -> list[tuple]:
    """Rows of an INE comuna sheet that belong to an RM comuna (column 4 = code)."""
    return [f for f in filas if f and len(f) > 6 and isinstance(f[4], int)
            and es_comuna_rm(pd.Series([f[4]])).iloc[0]]


def csv_2017(archivo: str, interno: str, csv: str, columnas: list[str]):
    """Stream a CSV from INE's nested RAR without writing the 2.6 GB file to disk."""
    externo = subprocess.Popen(["bsdtar", "-xOf", str(descargar(archivo)), interno],
                               stdout=subprocess.PIPE)
    lector = subprocess.Popen(["bsdtar", "-xOf", "-", csv], stdin=externo.stdout,
                              stdout=subprocess.PIPE)
    externo.stdout.close()
    yield from pd.read_csv(lector.stdout, sep=";", usecols=columnas, dtype="int64",
                           chunksize=1_000_000)
    if lector.wait() or externo.wait():
        sys.exit(f"bsdtar failed while reading {csv} from {archivo}")


def mudanzas_2017(codigos: list[int]) -> pd.DataFrame:
    partes, residentes_rm, ambiguos = [], 0, 0
    for bloque in csv_2017("csv-personas-censo-2017.zip", "microdato_censo2017-personas.rar",
                           "Microdato_Censo2017-Personas.csv", COLS_P17):
        partes.append(pares_2017(bloque))
        habitual = bloque["COMUNA"].where(bloque["P10"].isin((1, 2)), bloque["P10COMUNA"])
        en_rm = es_comuna_rm(habitual) & bloque["P10"].isin((1, 2, 3))
        residentes_rm += int(en_rm.sum())
        ambiguos += int((en_rm & (bloque["P10"] == 3) & (bloque["P11"] == 2)).sum())
    pares = pd.concat(partes).groupby(["codigo_origen", "codigo_destino"], as_index=False).sum()
    print(f"2017: RM usual residents with a known comuna = {residentes_rm:,}; "
          f"in the matrix = {int(pares['personas'].sum()):,}; "
          f"dropped (counted elsewhere, 'this comuna' 5 years ago) = {ambiguos:,}")
    return completar_rm(pares, codigos)


def viviendas_2017() -> pd.Series:
    cuenta = pd.Series(dtype="int64")
    for bloque in csv_2017("csv-viviendas-censo-2017.zip", "microdato_censo2017-viviendas.rar",
                           "Microdato_Censo2017-Viviendas.csv", ["COMUNA", "P01"]):
        bloque = bloque[es_comuna_rm(bloque["COMUNA"]) & bloque["P01"].isin(P01_VIVIENDA)]
        cuenta = cuenta.add(bloque.groupby("COMUNA").size(), fill_value=0)
    return cuenta.astype(int)


def poblacion_viviendas() -> pd.DataFrame:
    # 2024: D5 sheet "2" col 6 = población censada; V1 sheet "2" col 6 = viviendas censadas.
    pob24 = {f[4]: (f[5], f[6]) for f in filas_comuna(hoja("D5_Migracion-interna.xlsx", "2"))}
    viv24 = {f[4]: f[6] for f in
             filas_comuna(hoja("V1_Viviendas-y-hogares-censados.xlsx", "2"))}
    # 2017: sheet "2" col 7 = residentes habituales (comparable with the 2024 de jure count).
    pob17 = {f[4]: (f[5], f[7]) for f in filas_comuna(
        hoja("Poblacion-censada-y-residentes-habituales-Censo-2017.xlsx", "2"))}
    viv17 = viviendas_2017()

    if not (set(pob24) == set(viv24) == set(pob17) == set(viv17.index)):
        sys.exit("RM comuna codes differ between sources; check the raw files")
    filas = [(c, pob24[c][0], 2024, pob24[c][1], viv24[c]) for c in sorted(pob24)]
    filas += [(c, pob24[c][0], 2017, pob17[c][1], int(viv17[c])) for c in sorted(pob17)]
    return pd.DataFrame(filas, columns=["codigo", "comuna", "anio", "poblacion", "viviendas"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tabla = poblacion_viviendas()
    tabla.to_csv(OUT / "poblacion_viviendas.csv", index=False)
    codigos = sorted(tabla["codigo"].unique())

    m24 = completar_rm(matriz_2024(hoja("D5_Migracion-interna.xlsx", "2")), codigos)
    m24[COLUMNAS].to_csv(OUT / "mudanzas_2019_2024.csv", index=False)
    m17 = mudanzas_2017(codigos)
    m17[COLUMNAS].to_csv(OUT / "mudanzas_2012_2017.csv", index=False)

    for anio, m in (("2012-2017", m17), ("2019-2024", m24)):
        fuera = m[m["codigo_origen"] != m["codigo_destino"]]["personas"].sum()
        print(f"{anio}: {len(m)} pairs, moves between RM comunas = {fuera:,}, "
              f"stayers = {m['personas'].sum() - fuera:,}")
    print(tabla.groupby("anio")[["poblacion", "viviendas"]].sum())


if __name__ == "__main__":
    main()
