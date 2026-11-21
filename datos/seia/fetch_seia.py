"""Download every SEIA project of the Región Metropolitana (environmental impact assessment).

Source: Servicio de Evaluación Ambiental, https://seia.sea.gob.cl. The project search page
loads its table from a JSON endpoint:
    POST https://seia.sea.gob.cl/busqueda/buscarProyectoResumenAction.php
    form: selectRegion=13, offset, limit, orderColumn, orderDir (no session needed)
`offset` counts in steps of 10 rows: rows start at (offset - 1) * 10.

The site answers bursts with a JavaScript anti-bot challenge. This script does not try to pass
it: it asks for 100 rows at a time with a 10 s pause, waits a minute and asks again when the
answer is not JSON (3 attempts), then stops. The Excel export is not used (challenge, and capped at 1000 rows).

Usage (from the repo root):  .venv/bin/python -m datos.seia.fetch_seia
Raw pages are cached in data/raw/seia/ (ignored by git).
Output: data/seia/proyectos_rm.csv and data/seia/manifest.json.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import time
from collections import Counter

from datos.comun import ROOT, cut_de, descargar, escribir_manifiesto

URL = "https://seia.sea.gob.cl/busqueda/buscarProyectoResumenAction.php"
RAW = ROOT / "data" / "raw" / "seia"
OUT = ROOT / "data" / "seia"
PAGE = 100
PAUSE_S = 10.0
BACKOFF_S = 60.0  # wait this long after a challenge page, then ask again
RETRIES = 3
FORM = {"nombre": "", "titular": "", "folio": "", "selectRegion": "13", "selectComuna": "",
        "tipoPresentacion": "", "projectStatus": "", "PresentacionMin": "",
        "PresentacionMax": "", "sectores_economicos": "", "razoningreso": "",
        "id_tipoexpediente": "", "orderColumn": "EXPEDIENTE_ID", "orderDir": "ASC"}
COLUMNS = ["expediente_id", "nombre", "tipo_presentacion", "codigos_comuna", "comunas",
           "tipologia", "descripcion_tipologia", "titular", "inversion_musd",
           "fecha_presentacion", "estado", "url_ficha"]


def page(start: int, manifest: dict) -> dict:
    form = {**FORM, "offset": str(start // 10 + 1), "limit": str(PAGE)}
    path = RAW / f"pagina_{start:05d}.json"
    for attempt in range(RETRIES):
        body = descargar(URL, path, manifest, datos=form, pausa=PAUSE_S)
        try:
            return json.loads(body.decode("latin-1"))
        except json.JSONDecodeError:
            # A challenge page, not data: drop it, slow down and ask again. Never bypass it.
            path.unlink()
            print(f"row {start}: not JSON (attempt {attempt + 1}), waiting {BACKOFF_S:.0f} s")
            time.sleep(BACKOFF_S)
    raise SystemExit(f"SEIA did not answer JSON at row {start} after {RETRIES} attempts. "
                     "Wait a few minutes and rerun: cached pages are kept.")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    first = page(0, manifest)
    total = int(first["recordsTotal"])
    rows = list(first["data"])
    for start in range(PAGE, total, PAGE):
        rows += page(start, manifest)["data"]
    projects = {r["EXPEDIENTE_ID"]: r for r in rows}
    if len(projects) != total:
        raise SystemExit(f"SEIA: {len(projects)} unique projects, expected {total}")

    unmatched: Counter[str] = Counter()
    with (OUT / "proyectos_rm.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        for r in sorted(projects.values(), key=lambda r: int(r["EXPEDIENTE_ID"])):
            names = [n.strip() for n in (r["COMUNA_NOMBRE"] or "").split(",") if n.strip()]
            codes = [cut_de(n) for n in names]
            unmatched.update(n for n, c in zip(names, codes, strict=True) if c is None)
            investment = r["INVERSION_MM"]
            raw_date = r["FECHA_PRESENTACION_FORMAT"]
            date = (dt.datetime.strptime(raw_date, "%d/%m/%Y").date().isoformat()
                    if raw_date else "")
            w.writerow([r["EXPEDIENTE_ID"], r["EXPEDIENTE_NOMBRE"], r["WORKFLOW_DESCRIPCION"],
                        ";".join(c for c in codes if c), ";".join(names), r["TIPO_PROYECTO"],
                        r["DESCRIPCION_TIPOLOGIA"], r["TITULAR"],
                        "" if not investment else round(float(investment) / 1e6, 4),
                        date, r["ESTADO_PROYECTO"], r["EXPEDIENTE_URL_FICHA"]])
    escribir_manifiesto(OUT, "SEIA, Servicio de Evaluación Ambiental (https://seia.sea.gob.cl)",
                        manifest, proyectos=total)
    print(f"{total} projects; states: {Counter(r['ESTADO_PROYECTO'] for r in projects.values())}")
    if unmatched:
        print(f"names outside the RM (kept in 'comunas', no CUT): {dict(unmatched)}")


if __name__ == "__main__":
    main()
