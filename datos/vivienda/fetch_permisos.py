"""Download MINVU's housing permits table and build permits per RM comuna and year.

Usage (from the repo root):  .venv/bin/python -m datos.vivienda.fetch_permisos
Needs data/censo/poblacion_viviendas.csv for the comuna names and codes.
Raw file cached in data/raw/vivienda/ (ignored by git) and checked against its SHA-256.
Output: data/vivienda/permisos_vivienda.csv
  codigo, comuna, anio, viviendas, departamentos, casas, m2   (2002-2024, definitive years)
"""

from __future__ import annotations

import csv
from pathlib import Path

import openpyxl

from datos.censo.fetch_censo import descargar
from datos.vivienda.vivienda import HOJAS, leer_permisos

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "vivienda"
OUT = ROOT / "data" / "vivienda"
COMUNAS = ROOT / "data" / "censo" / "poblacion_viviendas.csv"

ARCHIVO = "permisos_vivienda_comuna.xlsx"
# MINVU CECT, "Viviendas unidades y superficie según año y comuna 2002 a sep 2026",
# downloaded on 2026-11-21. The table says: "Los datos registrados hasta el año 2024 son
# definitivos"; 2025 is preliminary and 2026 partial, so they are left out.
FUENTES = {ARCHIVO: (
    "https://catalogo.minvu.cl/cgi-bin/koha/opac-retrieve-file.pl?id=d40a41546b26b2a7fe5f1440af6e6ff2",
    "786f0d9f1da88862dc267516b9cbdd26cb10a224cb8d091254379d426646e5dc")}
ANIOS = list(range(2002, 2025))


def comunas() -> dict[str, int]:
    with COMUNAS.open(encoding="utf-8", newline="") as fh:
        return {f["comuna"]: int(f["codigo"]) for f in csv.DictReader(fh) if f["anio"] == "2024"}


def main() -> None:
    codigos = comunas()
    nombre_de = {c: n for n, c in codigos.items()}
    # data_only: read the values Excel cached for the region total formulas.
    libro = openpyxl.load_workbook(descargar(ARCHIVO, FUENTES, RAW), read_only=True,
                                   data_only=True)
    hojas = {h: list(libro[h].iter_rows(values_only=True)) for h in HOJAS.values()}
    permisos = leer_permisos(hojas, codigos, ANIOS)

    OUT.mkdir(parents=True, exist_ok=True)
    columnas = list(HOJAS)
    with (OUT / "permisos_vivienda.csv").open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.writer(fh)
        escritor.writerow(["codigo", "comuna", "anio", *columnas])
        for codigo in sorted(nombre_de):
            for anio in ANIOS:
                p = permisos[(codigo, anio)]
                escritor.writerow([codigo, nombre_de[codigo], anio, *(p[c] for c in columnas)])
    for anio in (2012, 2017, 2021, 2023, 2024):
        print(anio, sum(permisos[(c, anio)]["viviendas"] for c in nombre_de))


if __name__ == "__main__":
    main()
