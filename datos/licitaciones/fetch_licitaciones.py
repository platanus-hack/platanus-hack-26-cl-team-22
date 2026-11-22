"""Download (with SHA-256 cache) and aggregate ChileCompra monthly ZIPs for the 52 RM communes.

Source: ChileCompra Open Data (Datos Abiertos), monthly tender dumps at
https://transparenciachc.blob.core.windows.net/lic-da/{year}-{month}.zip.

Usage (from repo root):
    .venv/bin/python -m datos.licitaciones.fetch_licitaciones --desde 2024-01 --hasta 2024-12
    .venv/bin/python -m datos.licitaciones.fetch_licitaciones --solo-locales
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path

from datos.licitaciones.esquema import (
    CHILECOMPRA_URL_TEMPLATE,
    ROOT,
    DedupTender,
    TenderLineRecord,
    aggregate_tenders,
    deduplicate_tenders,
    iter_records_from_zip,
    load_rm_commune_index,
)

RAW = ROOT / "data" / "raw" / "licitaciones"
OUT = ROOT / "data" / "licitaciones"
_YM_RE = re.compile(r"^(\d{4})-(\d{1,2})$")
DETAIL_CSV_NAME = "licitaciones_detalle.csv"
DETAIL_FIELDS = [
    "codigo_comuna",
    "anio",
    "codigo_externo",
    "nombre",
    "estado",
    "estado_chilecompra",
    "sector",
    "monto_estimado_clp",
    "monto_adjudicado_clp",
    "numero_oferentes",
    "dias_pub_cierre",
    "dias_pub_adj",
]


def month_range(desde: str, hasta: str) -> list[tuple[int, int]]:
    """Return inclusive list of (year, month) pairs from YYYY-MM bounds."""
    m_start = _YM_RE.match(desde.strip())
    m_end = _YM_RE.match(hasta.strip())
    if not m_start or not m_end:
        raise ValueError("Expected YYYY-MM format for --desde and --hasta")
    y0, mo0 = int(m_start.group(1)), int(m_start.group(2))
    y1, mo1 = int(m_end.group(1)), int(m_end.group(2))
    if not (1 <= mo0 <= 12 and 1 <= mo1 <= 12) or y0 < 2000 or y1 > 2100:
        raise ValueError("Year must be in [2000, 2100] and month in [1, 12]")
    if (y0, mo0) > (y1, mo1):
        raise ValueError(f"--desde ({desde}) cannot be after --hasta ({hasta})")

    months: list[tuple[int, int]] = []
    y, mo = y0, mo0
    while (y, mo) <= (y1, mo1):
        months.append((y, mo))
        if mo == 12:
            y += 1
            mo = 1
        else:
            mo += 1
    return months


def _file_manifest_entry(path: Path, url: str, *, descargado: str | None) -> dict[str, object]:
    body = path.read_bytes()
    return {
        "url": url,
        "descargado": descargado,
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
    }


def load_previous_download_dates(manifest_path: Path) -> dict[str, str]:
    """Map sha256 -> recorded download date from an existing manifest ({} if absent)."""
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    files = data.get("archivos") if isinstance(data, dict) else None
    if not isinstance(files, dict):
        return {}
    dates: dict[str, str] = {}
    for entry in files.values():
        if not isinstance(entry, dict):
            continue
        sha, date = entry.get("sha256"), entry.get("descargado")
        if isinstance(sha, str) and isinstance(date, str) and date:
            dates[sha] = date
    return dates


def _local_manifest_entry(
    path: Path, url: str, previous_dates: Mapping[str, str]
) -> dict[str, object]:
    """Entry for a file not downloaded in this run.

    The file mtime is not a download date (an LFS checkout sets it to the clone date), so the
    date comes only from a previous manifest record with the same sha256; otherwise it is
    unknown (None).
    """
    entry = _file_manifest_entry(path, url, descargado=None)
    entry["descargado"] = previous_dates.get(str(entry["sha256"]))
    return entry


def download_month_zip(
    year: int,
    month: int,
    raw_dir: Path = RAW,
    *,
    force: bool = False,
    delay_s: float = 0.5,
    previous_dates: Mapping[str, str] | None = None,
) -> tuple[Path, dict[str, object]]:
    """Download one ChileCompra monthly ZIP with local caching and ZIP header check.

    A genuinely new download records today's date; a cached file keeps the date recorded for
    its sha256 in `previous_dates` (None when there is no record).
    """
    url = CHILECOMPRA_URL_TEMPLATE.format(year=year, month=month)
    zip_path = raw_dir / f"{year}-{month}.zip"
    if not zip_path.exists() or force:
        raw_dir.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "team22-simulation/1.0"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read()
        if not body.startswith(b"PK\x03\x04"):
            raise ValueError(f"Downloaded payload from {url} is not a valid ZIP archive")
        zip_path.write_bytes(body)
        if delay_s > 0:
            time.sleep(delay_s)
        return zip_path, _file_manifest_entry(
            zip_path, url, descargado=dt.date.today().isoformat()
        )

    return zip_path, _local_manifest_entry(zip_path, url, previous_dates or {})


def _infer_year_from_zip_name(zip_path: Path) -> int | None:
    match = _YM_RE.match(zip_path.stem)
    return int(match.group(1)) if match else None


def _csv_val(val: object) -> object:
    return "" if val is None else val


def write_detail_csv(tenders: Sequence[DedupTender], path: Path) -> None:
    """One row per deduplicated tender, sorted by commune, year and code.

    `estado` is the state the aggregates count it under (adjudicada / fallida / abierta);
    `estado_chilecompra` keeps the raw label. An empty `monto_adjudicado_clp` means no line
    reported an awarded peso amount.
    """
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=DETAIL_FIELDS)
        writer.writeheader()
        for t in sorted(tenders, key=lambda t: (t.codigo_comuna, t.anio, t.codigo_externo)):
            writer.writerow({
                "codigo_comuna": t.codigo_comuna,
                "anio": t.anio,
                "codigo_externo": t.codigo_externo,
                "nombre": t.nombre,
                "estado": t.estado_resumen,
                "estado_chilecompra": t.estado,
                "sector": t.sector,
                "monto_estimado_clp": _csv_val(t.monto_estimado),
                "monto_adjudicado_clp": (
                    round(t.monto_adjudicado, 2) if t.con_monto_adjudicado else ""
                ),
                "numero_oferentes": _csv_val(t.numero_oferentes),
                "dias_pub_cierre": _csv_val(t.dias_pub_cierre),
                "dias_pub_adj": _csv_val(t.dias_pub_adj),
            })


def build_tables_from_zips(
    zip_paths: Sequence[Path],
    out_dir: Path,
    commune_index: Mapping[str, str],
    manifest_files: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Parse local ChileCompra ZIP files, aggregate RM metrics, and write CSVs + manifest.

    Writes the per-tender detail (`licitaciones_detalle.csv`) from the same deduplicated
    tenders the aggregates count, so their per-commune counts match exactly.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    diagnostics: dict[str, int] = {
        "total_filas": 0,
        "filas_rm": 0,
        "filas_sin_comuna_rm": 0,
        "outliers_monto_filtrados": 0,
    }
    records: list[TenderLineRecord] = []
    for zip_path in sorted(zip_paths):
        default_year = _infer_year_from_zip_name(zip_path)
        records.extend(
            iter_records_from_zip(
                zip_path,
                commune_index,
                default_year=default_year,
                diagnostics=diagnostics,
            )
        )

    tenders = deduplicate_tenders(records)
    year_metrics, sector_metrics = aggregate_tenders(tenders)
    write_detail_csv(tenders, out_dir / DETAIL_CSV_NAME)

    year_csv = out_dir / "resumen_comuna_anio.csv"
    year_fields = [
        "codigo_comuna",
        "anio",
        "total_licitaciones",
        "adjudicadas",
        "fallidas",
        "cerradas",
        "tasa_adjudicacion",
        "mediana_dias_pub_cierre",
        "mediana_dias_pub_adj",
        "mediana_oferentes",
        "proporcion_oferente_unico",
        "monto_estimado_clp",
        "monto_adjudicado_clp",
    ]
    with year_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=year_fields)
        writer.writeheader()
        for row in year_metrics:
            data = asdict(row)
            writer.writerow({k: _csv_val(data[k]) for k in year_fields})

    sector_csv = out_dir / "resumen_sector_comuna.csv"
    sector_fields = [
        "codigo_comuna",
        "sector",
        "total_licitaciones",
        "adjudicadas",
        "fallidas",
        "monto_adjudicado_clp",
    ]
    with sector_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=sector_fields)
        writer.writeheader()
        for row in sector_metrics:
            writer.writerow(asdict(row))

    manifest = {
        "fuente": "ChileCompra Datos Abiertos (https://datos-abiertos.chilecompra.cl)",
        "url_plantilla": CHILECOMPRA_URL_TEMPLATE,
        "generado": dt.date.today().isoformat(),
        "diagnosticos": {
            **diagnostics,
            "filas_resumen_comuna_anio": len(year_metrics),
            "filas_resumen_sector_comuna": len(sector_metrics),
        },
        "archivos": manifest_files,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return manifest


def _manifest_key(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", default="2024-01", help="Start month YYYY-MM (default 2024-01)")
    parser.add_argument("--hasta", default="2024-12", help="End month YYYY-MM (default 2024-12)")
    parser.add_argument(
        "--solo-locales",
        action="store_true",
        help="Skip downloads and build tables only from existing ZIP files in --raw-dir",
    )
    parser.add_argument(
        "--forzar-descarga",
        action="store_true",
        help="Ignore cached ZIP files and download again",
    )
    parser.add_argument("--raw-dir", type=Path, default=RAW, help="Directory for cached ZIPs")
    parser.add_argument("--out-dir", type=Path, default=OUT, help="Directory for clean CSVs")
    args = parser.parse_args(argv)

    months = month_range(args.desde, args.hasta)
    commune_index = load_rm_commune_index()
    # Read before build_tables_from_zips overwrites the manifest.
    previous_dates = load_previous_download_dates(args.out_dir / "manifest.json")

    zip_paths: list[Path] = []
    manifest_files: dict[str, dict[str, object]] = {}
    if args.solo_locales:
        for year, month in months:
            candidate = args.raw_dir / f"{year}-{month}.zip"
            if candidate.exists():
                url = CHILECOMPRA_URL_TEMPLATE.format(year=year, month=month)
                zip_paths.append(candidate)
                manifest_files[_manifest_key(candidate)] = _local_manifest_entry(
                    candidate, url, previous_dates
                )
        if not zip_paths:
            raise SystemExit(
                f"No local ZIP files found in {args.raw_dir} for {args.desde}..{args.hasta}"
            )
    else:
        for year, month in months:
            path, meta = download_month_zip(
                year,
                month,
                args.raw_dir,
                force=args.forzar_descarga,
                previous_dates=previous_dates,
            )
            zip_paths.append(path)
            manifest_files[_manifest_key(path)] = meta

    manifest = build_tables_from_zips(zip_paths, args.out_dir, commune_index, manifest_files)
    diag = manifest["diagnosticos"]
    print(
        f"Processed {len(zip_paths)} ZIPs -> {diag['filas_rm']} RM lines, "
        f"{diag['filas_resumen_comuna_anio']} commune-year rows -> {args.out_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
