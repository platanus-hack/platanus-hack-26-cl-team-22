"""Download ARClim climate projections and risk components for the 52 RM communes.

Source: ARClim, Atlas de Riesgos Climáticos (Ministerio del Medio Ambiente), public API
documented in https://arclim.mma.gob.cl/media/learning/API_ARClim.pdf (December 2025).

Two kinds of data:
- Series: one annual series per climate-model run (GCM ensemble member), 1970-2069, per
  commune, indicator and scenario (`/api/series/{indicator}/comunas/{code}/annual/{scenario}/`).
  The simulation samples one run per replica, so climate uncertainty comes from real models.
- Components: ARClim's own hazard, exposure and vulnerability attributes per commune
  (`/api/datos/comunas/json/?attributes=...`). They are inputs, not results: the simulation
  computes its own risk indices.

Usage (from the repo root):  .venv/bin/python -m datos.arclim.fetch_arclim
Raw responses are cached in data/raw/arclim/ (ignored by git); rerunning skips cached files.
Output: data/arclim/series_{indicator}_{scenario}.csv.gz, data/arclim/componentes_comuna.csv
and data/arclim/manifest.json (URL, download date and SHA-256 of every raw response).
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import hashlib
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "arclim"
OUT = ROOT / "data" / "arclim"
COMMUNES = ROOT / "data" / "comunas_rm.csv"
API = "https://arclim.mma.gob.cl/api"
SCENARIOS = ("ssp245", "ssp585")
SEASON = "annual"

# indicator code -> why the simulation needs it
INDICATORS = {
    "pr_sum": "Precipitación acumulada anual (mm): oferta de agua.",
    "spi": "Índice estandarizado de precipitación: sequía meteorológica.",
    "drought_periods": "Frecuencia de sequía (%).",
    "eto_mean": "Evapotranspiración potencial (mm/día): demanda de agua.",
    "maximum_daily_precipitation": "Precipitación máxima diaria (mm): inundación.",
    "days_over_50mm": "Días con más de 50 mm: inundación.",
    "hot_days": "Días sobre 30 °C: enfriamiento de centros de datos.",
    "degdays_above_25": "Grados-día sobre 25 °C: demanda de enfriamiento.",
    "degdays_below_17_heating": "Grados-día de calefacción (17 °C): emisiones de leña.",
    "rsds_mean": "Radiación solar media (W/m²): potencial solar.",
}

# ARClim hazard / exposure / vulnerability per commune (read from the atlas map pages).
COMPONENTS = (
    "ind_amen_inundaciones_t10_pres", "ind_amen_inundaciones_t10_fut",
    "ind_amen_inundaciones_t10_delta", "ind_exp_inundaciones_norm",
    "ind_vuln_inundaciones_norm", "ind_riesgo_inundaciones_t10_pres_norm",
    "ind_riesgo_inundaciones_t10_delta",
    "amen_sequia_combinada_pres", "amen_sequia_combinada_fut", "amen_sequia_combinada_delta",
    "exp_sequia_combinada", "vuln_sequia_combinada", "riesgo_sequia_combinada_pres",
    "riesgo_sequia_combinada_delta",
    "asentamientos_ind_amen_aguaurb_pres_estandar", "asentamientos_ind_amen_aguaurb_fut_estandar",
    "asentamientos_ind_amen_aguaurb_delta", "asentamientos_ind_sens_aguaurb_estandar",
    "asentamientos_ind_resiliencia_aguarur", "asentamientos_ind_riesgo_aguaurb_pres_estandar",
    "asentamientos_ind_riesgo_aguaurb_delta",
    # energia_solar_amen exists on the atlas map but the API answers 500 for it (2026-11-21).
    "energia_solar_expo", "energia_solar_sensi", "energia_solar_riesgo",
)


def communes() -> list[tuple[str, str]]:
    with COMMUNES.open(encoding="utf-8-sig", newline="") as fh:
        return [(r["codigo_comuna"], r["comuna"]) for r in csv.DictReader(fh)]


def fetch(url: str, path: Path, manifest: dict) -> dict:
    """GET url as JSON, cached at path; records URL, date and SHA-256 in the manifest."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "team22-simulation/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
        path.write_bytes(body)
        time.sleep(0.2)  # be gentle with a public service
    body = path.read_bytes()
    manifest[str(path.relative_to(ROOT))] = {
        "url": url,
        "descargado": dt.date.fromtimestamp(path.stat().st_mtime).isoformat(),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    data = json.loads(body)
    return data.get("data", data)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    rm = communes()
    names = dict(rm)

    for indicator in INDICATORS:
        for scenario in SCENARIOS:
            rows, years = [], None
            for code, _ in rm:
                url = f"{API}/series/{indicator}/comunas/{code}/{SEASON}/{scenario}/"
                d = fetch(url, RAW / "series" / indicator / scenario / f"{code}.json", manifest)
                y = [int(v) for v in d["years"]]
                if years is None:
                    years = y
                elif y != years:
                    raise SystemExit(f"{indicator}/{scenario}/{code}: years differ")
                for run_name, gcm, run, values in zip(d["name"], d["gcms"], d["runs"],
                                                      d["series"], strict=True):
                    rows.append([code, names[code], gcm, run, run_name, *values])
            out = OUT / f"series_{indicator}_{scenario}.csv.gz"
            with gzip.open(out, "wt", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["codigo_comuna", "comuna", "gcm", "corrida", "nombre", *years])
                w.writerows(rows)
            print(f"{out.relative_to(ROOT)}: {len(rows)} filas")

    attrs = ",".join(("ComCod", "NOM_COMUNA", *COMPONENTS))
    d = fetch(f"{API}/datos/comunas/json/?attributes={attrs}",
              RAW / "componentes_comunas.json", manifest)
    columns = d["columns"]
    with (OUT / "componentes_comuna.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["codigo_comuna", "comuna", *COMPONENTS])
        by_code = {str(int(r[0])): r for r in d["values"]}
        for code, name in rm:
            r = by_code[code]
            w.writerow([code, name, *("" if r[columns.index(c)] is None else r[columns.index(c)]
                                      for c in COMPONENTS)])

    (OUT / "manifest.json").write_text(json.dumps(
        {"fuente": "ARClim, Ministerio del Medio Ambiente (https://arclim.mma.gob.cl)",
         "documentacion_api": "https://arclim.mma.gob.cl/media/learning/API_ARClim.pdf",
         "indicadores": INDICATORS, "escenarios": list(SCENARIOS), "archivos": manifest},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(manifest)} respuestas en el manifiesto")


if __name__ == "__main__":
    main()
