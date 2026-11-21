"""Download the SMA sanctioning processes and keep those in the Región Metropolitana.

Source: Superintendencia del Medio Ambiente, SNIFA open data (https://snifa.sma.gob.cl/DatosAbiertos),
which links a public Google Drive folder with `Sancionatorios.csv`, regenerated daily.
The CSV is `;`-separated, ISO-8859-1, dates dd-mm-yyyy. One row = one process x regulated unit,
so a process can appear more than once. Fines are in UTA and empty when there is no fine.

Usage (from the repo root):  .venv/bin/python -m datos.sma.fetch_sancionatorios
Output: data/sma/procesos_rm.csv and data/sma/manifest.json.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
from collections import Counter

from datos.comun import ROOT, cut_de, descargar, escribir_manifiesto

# Drive file id of Sancionatorios.csv in the folder linked from SNIFA (2026-11-21). If SMA
# re-uploads it, find the new id at https://drive.google.com/embeddedfolderview?id=1O7o60LzQ-qH8xiK_-Ofqw_mZzti_gbEr
FILE_ID = "1hPEwmUFZpmD7xFbJy-kjhhzjplnUB1mH"
URL = f"https://drive.usercontent.google.com/download?id={FILE_ID}&export=download&confirm=t"
RAW = ROOT / "data" / "raw" / "sma"
OUT = ROOT / "data" / "sma"
FIELDS = ["ProcesoSancionId", "Expediente", "ProcesoSancionTipoNombre", "ProcesoSancionEstado",
          "FechaInicio", "FechaTermino", "MultaTotalUTA", "UnidadFiscalizableId", "Nombre",
          "CategoriaEconomicaNombre", "SubCategoriaEconomicaNombre", "Latitud", "Longitud",
          "LinkSNIFA"]


def iso(value: str) -> str:
    return dt.datetime.strptime(value, "%d-%m-%Y").date().isoformat() if value else ""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    body = descargar(URL, RAW / "Sancionatorios.csv", manifest).decode("iso-8859-1")
    rows = [r for r in csv.DictReader(io.StringIO(body), delimiter=";")
            if (r.get("RegionNombre") or "").strip() == "Región Metropolitana"]
    unmatched = Counter()
    with (OUT / "procesos_rm.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["codigo_comuna", "comuna", *FIELDS])
        for r in rows:
            code = cut_de(r["ComunaNombre"])
            if code is None:
                unmatched[r["ComunaNombre"]] += 1
            values = {f: (r.get(f) or "").strip() for f in FIELDS}
            values["FechaInicio"] = iso(values["FechaInicio"])
            values["FechaTermino"] = iso(values["FechaTermino"])
            w.writerow([code or "", r["ComunaNombre"].strip(), *values.values()])
    escribir_manifiesto(OUT, "Superintendencia del Medio Ambiente, SNIFA datos abiertos "
                        "(https://snifa.sma.gob.cl/DatosAbiertos)", manifest)
    print(f"{len(rows)} RM rows, {len({r['ProcesoSancionId'] for r in rows})} processes, "
          f"{len({cut_de(r['ComunaNombre']) for r in rows} - {None})} communes; "
          f"unmatched names: {dict(unmatched)}")


if __name__ == "__main__":
    main()
