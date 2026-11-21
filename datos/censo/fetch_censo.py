"""Download INE census files and build the RM move matrices and comuna totals.

Usage (from the repo root):  .venv/bin/python -m datos.censo.fetch_censo
Raw files are cached in data/raw/censo/ (ignored by git); delete one to download it again.
Outputs in data/censo/:
  mudanzas_2012_2017.csv   Censo 2017, built from person microdata
  mudanzas_2019_2024.csv   Censo 2024, reshaped from the INE table D5 (sheet "2")
  poblacion_viviendas.csv  population and dwellings per comuna, both censuses
  flujos_externos.csv      people entering or leaving each RM comuna, both periods
  proyeccion_ine.csv       INE official population projection per comuna, 2017-2035
  viviendas_ocupacion_2024.csv  census 2024 dwellings per comuna by occupancy (INE table V1)
  stock_extranjero.csv     foreign-born residents per comuna in 2017, and those who arrived
                           before 2012 (network rule of the moves simulation)
Needs pandas, openpyxl, requests and `bsdtar` (the 2017 files are nested RAR archives).
Never fills gaps: anything missing stays out and is reported in data/censo/README.md.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import time
from pathlib import Path

import openpyxl
import pandas as pd
import requests

from datos.censo.censo import (
    COLUMNAS,
    EXTERNOS,
    completar_rm,
    es_comuna_rm,
    externos_2017,
    externos_2024,
    matriz_2024,
    pares_2017,
    stock_extranjero_2017,
    sumar_proyeccion,
)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "censo"
OUT = ROOT / "data" / "censo"

INE17 = ("https://www.ine.gob.cl/docs/default-source/censo-de-poblacion-y-vivienda/bbdd/"
         "censo-2017/csv/")
CENSO24 = "https://censo2024.ine.gob.cl/wp-content/uploads/2025/"
# name -> (url, SHA-256 of the file downloaded on 2026-11-21). A digest mismatch stops the
# build: the published tables in data/censo/ were checked against exactly these bytes.
FUENTES = {
    "D5_Migracion-interna.xlsx": (
        CENSO24 + "04/D5_Migracion-interna.xlsx",
        "8c1054de17731b3f17d0bf75f961901318389eef77d1eda026b21173856a47d5"),
    "V1_Viviendas-y-hogares-censados.xlsx": (
        CENSO24 + "03/V1_Viviendas-y-hogares-censados.xlsx",
        "19d5a5bb5b199c1b72714bfeade361e3493a76a350586d675d479a0564fe2b94"),
    "Poblacion-censada-y-residentes-habituales-Censo-2017.xlsx": (
        CENSO24 + "04/Poblacion-censada-y-residentes-habituales-Censo-2017.xlsx",
        "ea5aa0f3a1bad6acce93252e7f1e590f11dd721d1331eb71e6b84597f2bab297"),
    "csv-personas-censo-2017.zip": (
        INE17 + "csv-personas-censo-2017.zip",
        "69869fbb04d11912f5e08235700f7ea1e7cb3ae753f12188e4cff041cdbcfcd5"),
    "csv-viviendas-censo-2017.zip": (
        INE17 + "csv-viviendas-censo-2017.zip",
        "5c68e936aec3fceff15750118d701954c6f25fa3e85ce8720fabac44708b987b"),
    "estimaciones-y-proyecciones-2002-2035-comunas.xlsx": (
        ("https://www.ine.gob.cl/docs/default-source/proyecciones-de-poblacion/"
         "cuadros-estadisticos/base-2017/estimaciones-y-proyecciones-2002-2035-comunas.xlsx"),
        "de4ed9522031fad091dd2a51b3215bba685ebb851a14fb7421078ba927aa7ec1"),
}
PROYECCION_ANIOS = list(range(2017, 2036))
HEADERS = {"User-Agent": "Mozilla/5.0 (research script; hackathon census data)"}

COLS_P17 = ["COMUNA", "P10", "P10COMUNA", "P11", "P11COMUNA", "P12", "P12A_LLEGADA"]
# Censo 2017 dwelling type P01: 1-7 private dwellings, 8 collective; 9 and 10 are
# "operativo personas en tránsito / calle" and are not dwellings.
P01_VIVIENDA = range(1, 9)


def verificar(ruta: Path, esperado: str) -> Path:
    digest = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            digest.update(bloque)
    if digest.hexdigest() != esperado:
        sys.exit(f"{ruta} has SHA-256 {digest.hexdigest()}, expected {esperado}. INE may have "
                 "republished it, or the cache is corrupt: delete it and rerun; if the new file "
                 "is intended, update FUENTES and recheck the totals in data/censo/README.md")
    return ruta


def descargar(nombre: str, fuentes: dict | None = None, raw: Path | None = None) -> Path:
    """Return the cached raw file, downloading it once with retries; checks its SHA-256.

    `fuentes` maps file name -> (url, sha256) and `raw` is the cache folder; both default to
    the census ones so other datasets can reuse the same download rules.
    """
    destino = (raw or RAW) / nombre
    url, sha = (fuentes or FUENTES)[nombre]
    if destino.exists() and destino.stat().st_size > 0:
        return verificar(destino, sha)
    destino.parent.mkdir(parents=True, exist_ok=True)
    ultimo = None
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
                    return verificar(destino, sha)
                ultimo = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            ultimo = repr(e)
    sys.exit(f"Could not download {url}: {ultimo}")


def hoja(nombre: str, pestana: str, fuentes: dict | None = None,
         raw: Path | None = None) -> list[tuple]:
    libro = openpyxl.load_workbook(descargar(nombre, fuentes, raw), read_only=True)
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
    try:
        yield from pd.read_csv(lector.stdout, sep=";", usecols=columnas, dtype="int64",
                               chunksize=1_000_000)
    finally:
        # Always reap both children, also when parsing fails mid-stream. Callers write
        # nothing until the generator is exhausted, so a failed read leaves no output.
        lector.stdout.close()
        fallo = [lector.wait(), externo.wait()]
    if any(fallo):
        sys.exit(f"bsdtar failed while reading {csv} from {archivo}")


def mudanzas_2017(codigos: list[int]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Internal move matrix, external flows 2012-2017 and foreign-born stock, in one pass."""
    partes, externos, residentes_rm, ambiguos = [], [], 0, 0
    stock: dict[int, list[int]] = {}
    for bloque in csv_2017("csv-personas-censo-2017.zip", "microdato_censo2017-personas.rar",
                           "Microdato_Censo2017-Personas.csv", COLS_P17):
        partes.append(pares_2017(bloque))
        externos.append(externos_2017(bloque))
        for c, (total, previo) in stock_extranjero_2017(bloque).items():
            acum = stock.setdefault(c, [0, 0])
            acum[0] += total
            acum[1] += previo
        habitual = bloque["COMUNA"].where(bloque["P10"].isin((1, 2)), bloque["P10COMUNA"])
        en_rm = es_comuna_rm(habitual) & bloque["P10"].isin((1, 2, 3))
        residentes_rm += int(en_rm.sum())
        ambiguos += int((en_rm & (bloque["P10"] == 3) & (bloque["P11"] == 2)).sum())
    pares = pd.concat(partes).groupby(["codigo_origen", "codigo_destino"], as_index=False).sum()
    print(f"2017: RM usual residents with a known comuna = {residentes_rm:,}; "
          f"in the matrix = {int(pares['personas'].sum()):,}; "
          f"dropped (counted elsewhere, 'this comuna' 5 years ago) = {ambiguos:,}")
    ext = (pd.concat(externos).groupby("codigo")[EXTERNOS].sum()
           .reindex(codigos, fill_value=0).reset_index())
    return completar_rm(pares, codigos), ext, stock


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
    m17, ext17, stock = mudanzas_2017(codigos)
    m17[COLUMNAS].to_csv(OUT / "mudanzas_2012_2017.csv", index=False)

    ext24 = externos_2024(hoja("D5_Migracion-interna.xlsx", "2"))
    nombres = tabla.drop_duplicates("codigo").set_index("codigo")["comuna"]
    # V1 sheet "2": col 6 censadas, 7 particulares ocupadas, 8 desocupadas, 9 colectivas.
    with (OUT / "viviendas_ocupacion_2024.csv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("codigo,comuna,viviendas,particulares_ocupadas,particulares_desocupadas,"
                 "colectivas\n")
        for f in sorted(filas_comuna(hoja("V1_Viviendas-y-hogares-censados.xlsx", "2")),
                        key=lambda f: f[4]):
            fh.write(f"{f[4]},{nombres[f[4]]},{f[6]},{f[7]},{f[8]},{f[9]}\n")
    with (OUT / "stock_extranjero.csv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("codigo,comuna,nacidos_extranjero_2017,llegaron_antes_2012\n")
        for c in codigos:
            total, previo = stock.get(c, [0, 0])
            fh.write(f"{c},{nombres[c]},{total},{previo}\n")
    print("foreign-born RM 2017:", sum(v[0] for v in stock.values()),
          "arrived before 2012:", sum(v[1] for v in stock.values()))
    externos = pd.concat([ext17.assign(periodo="2012-2017"), ext24.assign(periodo="2019-2024")])
    externos.insert(1, "comuna", externos["codigo"].map(nombres))
    externos = externos[["codigo", "comuna", "periodo", *EXTERNOS]]
    externos.sort_values(["periodo", "codigo"]).to_csv(OUT / "flujos_externos.csv", index=False)
    print(externos.groupby("periodo")[EXTERNOS].sum().T)

    libro = openpyxl.load_workbook(descargar("estimaciones-y-proyecciones-2002-2035-comunas.xlsx"),
                                   read_only=True)
    proy = sumar_proyeccion(list(libro.worksheets[0].iter_rows(values_only=True)),
                            PROYECCION_ANIOS)
    with (OUT / "proyeccion_ine.csv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("codigo,comuna,anio,poblacion\n")
        for codigo in codigos:
            for anio in PROYECCION_ANIOS:
                fh.write(f"{codigo},{nombres[codigo]},{anio},{proy[(codigo, anio)]}\n")

    for anio, m in (("2012-2017", m17), ("2019-2024", m24)):
        fuera = m[m["codigo_origen"] != m["codigo_destino"]]["personas"].sum()
        print(f"{anio}: {len(m)} pairs, moves between RM comunas = {fuera:,}, "
              f"stayers = {m['personas'].sum() - fuera:,}")
    print(tabla.groupby("anio")[["poblacion", "viviendas"]].sum())


if __name__ == "__main__":
    main()
