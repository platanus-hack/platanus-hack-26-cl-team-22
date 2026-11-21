"""Download INE vital statistics yearbooks and build births and deaths per RM comuna.

Usage (from the repo root):  .venv/bin/python -m datos.vitales.fetch_vitales
Needs data/censo/poblacion_viviendas.csv for the comuna names and codes.
Raw files are cached in data/raw/vitales/ (ignored by git) and checked against SHA-256.
Output: data/vitales/nacimientos_defunciones.csv (codigo, comuna, anio, nacimientos, defunciones)
"""

from __future__ import annotations

import csv
from pathlib import Path

from datos.censo.fetch_censo import hoja
from datos.vitales.vitales import leer_anuario

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "vitales"
OUT = ROOT / "data" / "vitales"
COMUNAS = ROOT / "data" / "censo" / "poblacion_viviendas.csv"

BASE = ("https://www.ine.gob.cl/docs/default-source/nacimientos-matrimonios-y-defunciones/"
        "cuadros-estadisticos/")
E = "estad%C3%ADsticas"
# year -> (file path under BASE, sheet name, SHA-256 of the file downloaded on 2026-11-21).
# 2016 births and deaths by comuna are in the "nacimientos" file.
ANUARIOS = {
    2012: (f"2012/anuario-de-{E}-vitales-2012.xlsx", "122-04",
           "9977e8d45e0ea9f2b279da82eff33ec5da41781c415c3f4db62e7c154f16e9a4"),
    2013: (f"2013/ine_anuario-de-{E}-vitales_2013_tabulados.xlsx", "1.2.2-04",
           "0a96a360e855921a2cf1216ed69a1dc7052b0ba625964fbeb4c2c685cd3c8408"),
    2014: (f"2014/ine_anuario-de-{E}-vitales_2014_tabulados.xlsx", "1.2.2-04",
           "ec82355ebde0bf1c8e5723ce7505866c14328f37f1bc4ede2ded830027d5f467"),
    2015: (f"2015/ine_anuario-de-{E}-vitales_2015_tabulados.xlsx", "1.2.2-04",
           "738a4987b6603219643b4baf0407fcf83b8ef43e2048dd62bd3059a6b035fdb3"),
    2016: (f"2016/ine_anuario-de-{E}-vitales_nacimientos_2016_tabulados.xlsx", "1.2.2-04",
           "713b5ec71413d579eee523f81cdf1c1bc15ac27dc6d4655875d2544295bd7374"),
    2017: (f"2017/anuario-de-{E}-vitales-2017-tabulados.xlsx", "1.2.2-04",
           "ea780c9fe66bcad4a03cbc602e919e096a1216a36a78a3aee3a5ee7a43a1c787"),
    2018: (f"2018/anuario-de-{E}-vitales-2018.xlsx", "122-04",
           "da7a0bb25f6980cf1117bd6cb65ce8c0b12b20ccbc92dc70c6859930c8c02c17"),
    2019: (f"2019/anuario-de-{E}-vitales-2019.xlsx", "122-04",
           "0fe74678684af9c30bb5830e196f76b27991f457ce9f98d7d9e231677e501c4d"),
    2020: (f"2020/anuario-de-{E}-vitales-2020.xlsx", "122-04",
           "23261c7d3074dcba798c3b23e992674857f793c16cb1effc5e8df22378837076"),
    2021: (f"2021/anuario-de-{E}-vitales-2021.xlsx", "122-04",
           "571012ecd6a7c468b47a42dbadcfce7144398c2ccaa9dfb846249e9f42a3a29b"),
    2022: (f"2022/anuario-de-{E}-vitales-2022.xlsx", "122-04",
           "43eca4eb6077046c645a438580dbe4da4916908dd24222361cbbd7287b2ce7e5"),
    2023: (f"2023/anuario-de-{E}-vitales-2023-nacimientos-y-defunciones.xlsx", "122-04",
           "5bcd6ddabe8bb7ae7eaa766c268dfacd67de299a180a85dbe875d4da3f1b49f9"),
}
FUENTES = {f"anuario_{anio}.xlsx": (BASE + ruta, sha) for anio, (ruta, _, sha) in ANUARIOS.items()}


def comunas() -> dict[str, int]:
    with COMUNAS.open(encoding="utf-8", newline="") as fh:
        return {f["comuna"]: int(f["codigo"]) for f in csv.DictReader(fh) if f["anio"] == "2024"}


def main() -> None:
    codigos = comunas()
    nombre_de = {c: n for n, c in codigos.items()}
    filas = []
    for anio, (_, pestana, _) in ANUARIOS.items():
        leidos = leer_anuario(hoja(f"anuario_{anio}.xlsx", pestana, FUENTES, RAW), codigos)
        filas += [(c, nombre_de[c], anio, *leidos[c]) for c in sorted(leidos)]
        print(f"{anio}: births {sum(v[0] for v in leidos.values()):,}, "
              f"deaths {sum(v[1] for v in leidos.values()):,}")
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "nacimientos_defunciones.csv").open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.writer(fh)
        escritor.writerow(["codigo", "comuna", "anio", "nacimientos", "defunciones"])
        escritor.writerows(filas)


if __name__ == "__main__":
    main()
