"""Download the DGA water-scarcity decrees and list the RM communes each one covers.

Source: Dirección General de Aguas (MOP), «Decretos de escasez»:
https://dga.mop.gob.cl/derechos-de-agua/proteccion-de-las-fuentes/decretos-de-escasez-2/
The page links one historical XLS (2008 onwards) whose filename carries a date, so the link is
read from the page on every run instead of being hardcoded.

The XLS has five columns (Año, Región, Decreto, Fecha de Caducidad, Cuenca/Comuna/Provincia):
- «Año» is written only on the first row of each year: it is filled down.
- The commune list is free text that mixes basins, provinces and communes. Province phrases
  («Provincia de Melipilla») are removed before matching commune names, so the province is not
  read as the commune; a row that names only an RM province covers all its communes.
- Santiago (13101) counts only on a literal «Comuna de Santiago», because «Región
  Metropolitana de Santiago» is common text.
- Rows tagged «Metropolitana» that name no RM commune or province (N°54/2020 and N°100/2020
  refer to O'Higgins and Valparaíso) are dropped and reported.

Usage (from the repo root):  .venv/bin/python -m datos.dga.fetch_decretos   (needs xlrd)
Output: data/dga/decretos_escasez_rm.csv (one row per decree and commune) and manifest.json.
"""
from __future__ import annotations

import csv
import re

from datos.comun import ROOT, clave, comunas_rm, descargar, escribir_manifiesto

PAGE = "https://dga.mop.gob.cl/derechos-de-agua/proteccion-de-las-fuentes/decretos-de-escasez-2/"
RAW = ROOT / "data" / "raw" / "dga"
OUT = ROOT / "data" / "dga"
PROVINCE = re.compile(r"[Pp]rovincias? (?:de |del )?(Santiago|Cordillera|Chacabuco|Maipo|"
                      r"Melipilla|Talagante)")
MONTHS = {m: i for i, m in enumerate(
    ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
     "octubre", "noviembre", "diciembre"), start=1)}
DATE = re.compile(r"(\d{1,2})\W+(?:de )?([a-záéíóú]+)\W+(?:de |del )?(\d{4})", re.IGNORECASE)


def iso_date(text: str) -> str:
    """'N° 178 de 17 de octubre de 2022' -> '2022-10-17'; '' when there is no date."""
    m = DATE.search(text)
    if not m or m.group(2).lower() not in MONTHS:
        return ""
    return f"{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def communes_in(text: str) -> tuple[list[str], bool]:
    """RM CUTs named in a decree's free text, and whether they come from a province."""
    rm = comunas_rm()
    provinces = sorted(set(PROVINCE.findall(text)))
    rest = clave(PROVINCE.sub(" ", text))
    hits = {r["codigo_comuna"] for r in rm
            if r["codigo_comuna"] != "13101" and clave(r["comuna"]) in rest}
    if re.search(r"[Cc]omuna de Santiago\b", PROVINCE.sub(" ", text)):
        hits.add("13101")
    if "13505" in hits and rest.count("sanpedro") == rest.count("sanpedrodelapaz"):
        hits.discard("13505")  # San Pedro de la Paz is in Biobío
    if hits or not provinces:
        return sorted(hits), False
    return sorted(r["codigo_comuna"] for r in rm if r["provincia"] in provinces), True


def main() -> None:
    import xlrd

    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    html = descargar(PAGE, RAW / "pagina.html", manifest).decode("utf-8", "replace")
    links = sorted(set(re.findall(r'https://[^"\']+Decretos_zonas_escasez_historico[^"\']+\.xls',
                                  html)))
    if len(links) != 1:
        raise SystemExit(f"Expected one historical XLS link on the DGA page, found {links}")
    xls = descargar(links[0], RAW / links[0].rsplit("/", 1)[1], manifest)
    sheet = xlrd.open_workbook(file_contents=xls).sheet_by_index(0)

    names = {r["codigo_comuna"]: r["comuna"] for r in comunas_rm()}
    out, dropped, year = [], [], None
    for i in range(1, sheet.nrows):
        year_cell, region, decree, expiry, text = (str(sheet.cell_value(i, c)).strip()
                                                   for c in range(5))
        if year_cell == "Año":
            continue
        if year_cell:
            year = int(float(year_cell))
        if "Metropolitana" not in region:
            continue
        codes, from_province = communes_in(text)
        if not codes:
            dropped.append(decree)
            continue
        out += [[year, decree, iso_date(decree), iso_date(expiry), code, names[code],
                 int(from_province), text] for code in codes]

    with (OUT / "decretos_escasez_rm.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["anio", "decreto", "fecha_decreto", "fecha_caducidad", "codigo_comuna",
                    "comuna", "por_provincia", "texto_original"])
        w.writerows(out)
    escribir_manifiesto(OUT, "Dirección General de Aguas, decretos de escasez hídrica", manifest,
                        filas_rm_descartadas=dropped)
    covered = {r[4] for r in out}
    print(f"{len({r[1] for r in out})} RM decrees, {len(covered)} communes; dropped: {dropped}")


if __name__ == "__main__":
    main()
