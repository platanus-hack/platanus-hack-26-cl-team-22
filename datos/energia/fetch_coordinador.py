"""Download power plants and substations in the RM from the Coordinador Eléctrico Nacional.

Source: Infotécnica, Coordinador Eléctrico Nacional (https://infotecnica.coordinador.cl). Its
web front end reads a public JSON API (no key):
    GET https://api-infotecnica.coordinador.cl/v1/centrales/extended/
    GET https://api-infotecnica.coordinador.cl/v1/subestaciones/extended/
    GET https://api-infotecnica.coordinador.cl/v1/comunas/      (comuna_id -> CUT)
    GET https://api-infotecnica.coordinador.cl/v1/barras/       (buses, named "... 110KV ...")
The API is undocumented and returns a snapshot of assets in operation, with no history.

Cleaning, all logged in the README:
- `tension_kv` is null for every substation in the API (1,278 nationwide, 2026-11-21), so it is
  filled with the highest voltage written in the names of the substation's buses.
- `fecha_inicio_operacion` is kept as the API writes it (eight formats and free text) and
  `anio_inicio_operacion` adds the year when one can be read.
- Coordinates outside the RM box on a row whose commune is in the RM are source errors (one plant
  sits in Antarctica): they are blanked, the row is kept.
- `comuna` uses the repo's names (data/comunas_rm.csv), e.g. "Tiltil" instead of "Til-Til".
CNE's Energía Abierta was tried first and could not be downloaded (2026-11-21): its API timed
out and the capacity file needs a Microsoft login.

Plants with no commune but coordinates are kept with an empty CUT (3 in the RM area).

Usage (from the repo root):  .venv/bin/python -m datos.energia.fetch_coordinador
Output: data/energia/centrales_rm.csv, data/energia/subestaciones_rm.csv, manifest.json.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict

from datos.comun import ROOT, comunas_rm, descargar, escribir_manifiesto

API = "https://api-infotecnica.coordinador.cl/v1"
RAW = ROOT / "data" / "raw" / "energia"
OUT = ROOT / "data" / "energia"
RM_REGION_CODE = 13
# Rough RM bounding box, used only to keep plants that have coordinates but no commune.
RM_BOX = {"lat": (-34.3, -32.9), "lon": (-71.8, -69.7)}
KV = re.compile(r"(\d+(?:[.,]\d+)?)\s*KV", re.IGNORECASE)
YEAR4 = re.compile(r"\b(19\d\d|20\d\d)\b")
DMY2 = re.compile(r"^\d{1,2}-\d{1,2}-(\d{2})$")


def get(path: str, manifest: dict) -> list[dict]:
    name = path.strip("/").replace("/", "_") + ".json"
    data = json.loads(descargar(f"{API}/{path}", RAW / name, manifest))
    return data if isinstance(data, list) else data["data"]


def in_box(lat: float | None, lon: float | None) -> bool:
    return (lat is not None and lon is not None
            and RM_BOX["lat"][0] <= lat <= RM_BOX["lat"][1]
            and RM_BOX["lon"][0] <= lon <= RM_BOX["lon"][1])


def bus_kv(buses: list[dict]) -> dict[int, float]:
    """Substation id -> highest voltage (kV) written in the names of its buses."""
    out: dict[int, float] = {}
    for b in buses:
        found = [float(x.replace(",", ".")) for x in KV.findall(b.get("nombre") or "")]
        if found:
            sid = b["id_subestacion"]
            out[sid] = max(out.get(sid, 0.0), *found)
    return out


def year_of(text: str | None) -> str:
    """Year in a free-form start date ('01-01-1991', '2011', '24-09-10', 'sept 2014'); '' if none."""
    text = (text or "").strip()
    if m := YEAR4.search(text):
        return m.group(1)
    if m := DMY2.match(text):
        yy = int(m.group(1))
        return str(2000 + yy if yy < 50 else 1900 + yy)
    return ""


def in_rm(row: dict, cut_of: dict[int, str]) -> bool:
    if row.get("comuna_id") in cut_of:
        return True
    return row.get("comuna_id") is None and in_box(row.get("latitud"), row.get("longitud"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    communes = get("comunas/", manifest)
    cut_of = {c["id"]: f"{c['code']:05d}" for c in communes
              if str(c["code"]).startswith(str(RM_REGION_CODE))}
    name_of = {r["codigo_comuna"]: r["comuna"] for r in comunas_rm()}
    kv_of = bus_kv(get("barras/", manifest))
    tables = {
        "centrales_rm.csv": (get("centrales/extended/", manifest),
                             ["id", "nombre", "tipo_central_nombre", "propietario_nombre",
                              "potencia_maxima", "fecha_inicio_operacion", "estado"]),
        "subestaciones_rm.csv": (get("subestaciones/extended/", manifest),
                                 ["id", "nombre", "tension_kv", "capacidad_mva",
                                  "tipo_configuracion", "fecha_inicio_operacion", "estado"]),
    }
    for r in tables["subestaciones_rm.csv"][0]:
        if r.get("tension_kv") is None:
            r["tension_kv"] = kv_of.get(r["id"])
    for filename, (rows, fields) in tables.items():
        kept = [r for r in rows if in_rm(r, cut_of)]
        blanked = 0
        with (OUT / filename).open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["codigo_comuna", "comuna", *fields, "anio_inicio_operacion",
                        "latitud", "longitud"])
            for r in sorted(kept, key=lambda r: r["id"]):
                cut = cut_of.get(r.get("comuna_id"), "")
                lat, lon = r.get("latitud"), r.get("longitud")
                if not in_box(lat, lon):
                    blanked += lat is not None or lon is not None
                    lat = lon = None
                w.writerow([cut, name_of.get(cut, r.get("comuna_nombre") or ""),
                            *(r.get(f) if r.get(f) is not None else "" for f in fields),
                            year_of(r.get("fecha_inicio_operacion")),
                            lat if lat is not None else "", lon if lon is not None else ""])
        print(f"{filename}: {len(kept)} rows, {sum(1 for r in kept if r.get('comuna_id') is None)}"
              f" without commune, {blanked} coordinates outside the RM blanked")
    mw: dict[str, float] = defaultdict(float)
    for r in tables["centrales_rm.csv"][0]:
        if in_rm(r, cut_of):
            mw[r["tipo_central_nombre"]] += r.get("potencia_maxima") or 0.0
    print({k: round(v, 1) for k, v in mw.items()})
    escribir_manifiesto(OUT, "Coordinador Eléctrico Nacional, Infotécnica "
                        "(https://infotecnica.coordinador.cl)", manifest)


if __name__ == "__main__":
    main()
