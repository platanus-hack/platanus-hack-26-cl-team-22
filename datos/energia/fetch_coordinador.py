"""Download power plants and substations in the RM from the Coordinador Eléctrico Nacional.

Source: Infotécnica, Coordinador Eléctrico Nacional (https://infotecnica.coordinador.cl). Its
web front end reads a public JSON API (no key):
    GET https://api-infotecnica.coordinador.cl/v1/centrales/extended/
    GET https://api-infotecnica.coordinador.cl/v1/subestaciones/extended/
    GET https://api-infotecnica.coordinador.cl/v1/comunas/      (comuna_id -> CUT)
The API is undocumented and returns a snapshot of assets in operation, with no history.
CNE's Energía Abierta was tried first and could not be downloaded (2026-11-21): its API timed
out and the capacity file needs a Microsoft login.

Plants with no commune but coordinates are kept with an empty CUT (3 in the RM area).

Usage (from the repo root):  .venv/bin/python -m datos.energia.fetch_coordinador
Output: data/energia/centrales_rm.csv, data/energia/subestaciones_rm.csv, manifest.json.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict

from datos.comun import ROOT, descargar, escribir_manifiesto

API = "https://api-infotecnica.coordinador.cl/v1"
RAW = ROOT / "data" / "raw" / "energia"
OUT = ROOT / "data" / "energia"
RM_REGION_CODE = 13
# Rough RM bounding box, used only to keep plants that have coordinates but no commune.
RM_BOX = {"lat": (-34.3, -32.9), "lon": (-71.8, -69.7)}


def get(path: str, manifest: dict) -> list[dict]:
    name = path.strip("/").replace("/", "_") + ".json"
    data = json.loads(descargar(f"{API}/{path}", RAW / name, manifest))
    return data if isinstance(data, list) else data["data"]


def in_rm(row: dict, cut_of: dict[int, str]) -> bool:
    if row.get("comuna_id") in cut_of:
        return True
    lat, lon = row.get("latitud"), row.get("longitud")
    return (row.get("comuna_id") is None and lat is not None and lon is not None
            and RM_BOX["lat"][0] <= lat <= RM_BOX["lat"][1]
            and RM_BOX["lon"][0] <= lon <= RM_BOX["lon"][1])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    communes = get("comunas/", manifest)
    cut_of = {c["id"]: f"{c['code']:05d}" for c in communes
              if str(c["code"]).startswith(str(RM_REGION_CODE))}
    tables = {
        "centrales_rm.csv": (get("centrales/extended/", manifest),
                             ["id", "nombre", "tipo_central_nombre", "propietario_nombre",
                              "potencia_maxima", "fecha_inicio_operacion", "estado"]),
        "subestaciones_rm.csv": (get("subestaciones/extended/", manifest),
                                 ["id", "nombre", "tension_kv", "capacidad_mva",
                                  "tipo_configuracion", "fecha_inicio_operacion", "estado"]),
    }
    for filename, (rows, fields) in tables.items():
        kept = [r for r in rows if in_rm(r, cut_of)]
        with (OUT / filename).open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["codigo_comuna", "comuna", *fields, "latitud", "longitud"])
            for r in sorted(kept, key=lambda r: r["id"]):
                w.writerow([cut_of.get(r.get("comuna_id"), ""), r.get("comuna_nombre") or "",
                            *(r.get(f) if r.get(f) is not None else "" for f in fields),
                            r.get("latitud") or "", r.get("longitud") or ""])
        print(f"{filename}: {len(kept)} rows, {sum(1 for r in kept if r.get('comuna_id') is None)}"
              " without commune")
    mw: dict[str, float] = defaultdict(float)
    for r in tables["centrales_rm.csv"][0]:
        if in_rm(r, cut_of):
            mw[r["tipo_central_nombre"]] += r.get("potencia_maxima") or 0.0
    print({k: round(v, 1) for k, v in mw.items()})
    escribir_manifiesto(OUT, "Coordinador Eléctrico Nacional, Infotécnica "
                        "(https://infotecnica.coordinador.cl)", manifest)


if __name__ == "__main__":
    main()
