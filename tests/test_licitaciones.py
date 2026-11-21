"""Tests for ChileCompra ingestion, schema parsing, and procurement credibility."""
from __future__ import annotations

import csv
import dataclasses
import datetime as dt
import io
import json
import os
import zipfile
from pathlib import Path

import pytest

from core.credibilidad import BetaCredibility
from core.licitaciones import (
    MAX_EFFECTIVE_N_ASSUMPTION,
    MIN_SAMPLE_ASSUMPTION,
    CommuneProcurementSummary,
    estimate_commune_credibility,
    load_procurement_summaries,
)
from datos.licitaciones import fetch_licitaciones
from datos.licitaciones.esquema import (
    CommuneYearMetrics,
    aggregate_records,
    classify_sector,
    iter_records_from_csv_stream,
    load_rm_commune_index,
    match_rm_commune,
    parse_chilecompra_date,
    parse_chilecompra_float,
)
from datos.licitaciones.fetch_licitaciones import (
    _file_manifest_entry,
    build_tables_from_zips,
    main,
    month_range,
)

ROOT = Path(__file__).resolve().parents[1]


def test_parse_chilecompra_float_and_date():
    assert parse_chilecompra_float("1.234.567,89") == pytest.approx(1234567.89)
    assert parse_chilecompra_float("1234,5") == pytest.approx(1234.5)
    assert parse_chilecompra_float("1234.5") == pytest.approx(1234.5)
    assert parse_chilecompra_float("--") is None
    assert parse_chilecompra_float("-500") is None
    assert parse_chilecompra_float("nan") is None

    assert parse_chilecompra_date("2024-05-10 14:30:00") == dt.date(2024, 5, 10)
    assert parse_chilecompra_date("15/03/2024") == dt.date(2024, 3, 15)
    assert parse_chilecompra_date("1900-01-01") is None
    assert parse_chilecompra_date("--") is None


def test_commune_is_attributed_only_when_buyer_is_its_municipality():
    idx = load_rm_commune_index()
    assert len(idx) == 52
    assert match_rm_commune("Ilustre Municipalidad de Puente Alto", idx) == "13201"
    assert match_rm_commune("I. Municipalidad de Maipú", idx) == "13119"
    assert match_rm_commune("I MUNICIPALIDAD DE TIL TIL", idx) == "13303"
    assert match_rm_commune("Municipalidad de Santiago", idx) == "13101"
    # Literal buyer names found in the 2024 dumps.
    assert match_rm_commune("I.MUNICIPALIDAD DE CERRO NAVIA", idx) == "13103"
    assert match_rm_commune("I MUNICIPALIDAD DE LA COMUNA DE EL BOSQUE", idx) == "13105"
    assert match_rm_commune("I MUNICIPALIDAD PEDRO AGUIRRE CERDA", idx) == "13121"
    assert match_rm_commune("ILUSTRE MUNICIPALIDAD  DE LA REINA", idx) == "13113"
    # Not the municipality: ministries, services and municipal corporations stay unmatched,
    # wherever their buying unit sits.
    assert match_rm_commune("Ministerio de Obras Públicas", idx) is None
    assert match_rm_commune("Ministerio de Salud", idx) is None
    assert match_rm_commune("DIRECCION SALUD RURAL", idx) is None
    assert match_rm_commune(
        "CORPORACION MUNICIPAL DE PENALOLEN PARA EL DESARROLO SOCIAL CORMUP", idx
    ) is None
    assert match_rm_commune(
        "Corporación del Deporte e Inclusión Social de la Ilustre Municipalidad de Cerro Navia",
        idx,
    ) is None
    # Municipalities outside the RM stay unmatched.
    assert match_rm_commune("Municipalidad de Valparaíso", idx) is None
    assert match_rm_commune("I MUNICIPALIDAD DE SAN PEDRO DE LA PAZ", idx) is None


def test_ministry_located_in_santiago_is_not_santiago_spending():
    idx = load_rm_commune_index()
    header = (
        "CodigoExterno;Nombre;Descripcion;ComunaUnidad;NombreOrganismo;CodigoEstado;"
        "FechaPublicacion;MontoEstimado;MontoLineaAdjudica;NumeroOferentes"
    )
    ministry = (
        "300-1-LP24;Insumos;Otro;Santiago;Ministerio de Salud;8;2024-02-01;1000;900;2"
    )
    hospital = (
        "300-2-LP24;Insumos;Otro;Santiago;Hospital San Juan de Dios;8;2024-02-01;1000;900;2"
    )
    muni = (
        "300-3-LE24;Plaza;Otro;Providencia;Municipalidad de Santiago;8;2024-02-01;1000;900;2"
    )
    diag: dict[str, int] = {}
    stream = io.StringIO(f"{header}\n{ministry}\n{hospital}\n{muni}")
    records = list(iter_records_from_csv_stream(stream, idx, diagnostics=diag))
    assert diag["filas_sin_comuna_rm"] == 2
    assert diag["filas_rm"] == 1
    assert [(r.codigo_externo, r.codigo_comuna) for r in records] == [("300-3-LE24", "13101")]


def test_sector_classification():
    assert classify_sector("Recambio de calefactores a leña", "Estufas pellet") == "aire_calefaccion"
    assert classify_sector("Agua potable rural", "Sistema APR") == "agua"
    assert classify_sector("Planta solar fotovoltaica", "Paneles energía") == "energia"
    assert classify_sector("Cámaras de teleprotección", "Seguridad comunal") == "seguridad"
    assert classify_sector("Pavimentación de veredas", "Obra civil") == "infraestructura"
    assert classify_sector("Servicio de cafetería", "Insumos varios") == "otros"


def test_line_item_deduplication_and_outlier_filtering():
    idx = load_rm_commune_index()
    header = (
        "CodigoExterno;Nombre;Descripcion;Nombre producto genrico;ComunaUnidad;"
        "NombreOrganismo;CodigoEstado;Estado;FechaPublicacion;FechaCierre;FechaAdjudicacion;"
        "MontoEstimado;MontoLineaAdjudica;NumeroOferentes;CantidadReclamos"
    )
    # Same tender with 2 line items: MontoEstimado is tender-level, MontoLineaAdjudica sums.
    line1 = (
        "100-1-LE24;Recambio estufas;Calefacción pellet;Estufa;El Bosque;"
        "Municipalidad de El Bosque;8;Adjudicada;2024-03-01;2024-03-11;2024-03-21;"
        "5000000;2000000;3;1"
    )
    line2 = (
        "100-1-LE24;Recambio estufas;Instalación pellet;Servicio;El Bosque;"
        "Municipalidad de El Bosque;8;Adjudicada;2024-03-01;2024-03-11;2024-03-21;"
        "5000000;2500000;3;1"
    )
    # Failed tender in same commune with extreme outlier (> $1 trillion).
    line3 = (
        "100-2-LE24;Cámaras seguridad;Vigilancia;Camara;;Ilustre Municipalidad de El Bosque;"
        "7;Desierta;2024-04-01;2024-04-06;;1000000;9999999999999;1;0"
    )
    # National organism without RM commune: excluded from RM output.
    line4 = (
        "999-1-LP24;Servicio nacional;Otro;Otro;;Subsecretaría General;"
        "8;Adjudicada;2024-04-01;2024-04-20;2024-05-01;1000000;800000;2;0"
    )
    csv_text = f"{header}\n{line1}\n{line2}\n{line3}\n{line4}"
    diag: dict[str, int] = {}
    records = list(iter_records_from_csv_stream(io.StringIO(csv_text), idx, diagnostics=diag))
    assert diag["total_filas"] == 4
    assert diag["filas_rm"] == 3
    assert diag["filas_sin_comuna_rm"] == 1
    assert diag["outliers_monto_filtrados"] == 1

    year_rows, sector_rows = aggregate_records(records)
    assert len(year_rows) == 1
    row = year_rows[0]
    assert row.codigo_comuna == "13105"
    assert row.anio == 2024
    assert row.total_licitaciones == 2
    assert row.adjudicadas == 1
    assert row.fallidas == 1
    assert row.cerradas == 2
    assert row.tasa_adjudicacion == pytest.approx(0.5)
    assert row.monto_estimado_clp == pytest.approx(6_000_000.0)
    assert row.monto_adjudicado_clp == pytest.approx(4_500_000.0)
    assert row.proporcion_oferente_unico == pytest.approx(0.5)
    assert {s.sector for s in sector_rows} == {"aire_calefaccion", "seguridad"}


def test_complaints_are_not_aggregated():
    # CantidadReclamos has no documented meaning per tender: it must not reach the output.
    assert "total_reclamos" not in {f.name for f in dataclasses.fields(CommuneYearMetrics)}
    assert "complaints_total" not in {
        f.name for f in dataclasses.fields(CommuneProcurementSummary)
    }


def test_file_manifest_entry_hashes_real_bytes(tmp_path: Path):
    path = tmp_path / "abc.zip"
    path.write_bytes(b"abc")
    entry = _file_manifest_entry(path, "https://example.invalid/abc.zip", descargado=None)
    # Standard SHA-256 test vector for b"abc" (FIPS 180-2).
    assert entry["sha256"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert entry["bytes"] == 3


def _write_month_zip(raw_dir: Path, name: str = "2024-1.zip") -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / name
    csv_body = (
        "CodigoExterno;Nombre;Descripcion;ComunaUnidad;NombreOrganismo;"
        "CodigoEstado;FechaPublicacion;FechaCierre;FechaAdjudicacion;"
        "MontoEstimado;MontoLineaAdjudica;NumeroOferentes;CantidadReclamos\n"
        "200-1-LE24;Agua potable;Red hídrica;Puente Alto;Municipalidad de Puente Alto;8;"
        "2024-01-05;2024-01-15;2024-01-25;3000000;2800000;4;0\n"
    )
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("lic_2024-1.csv", csv_body.encode("latin-1"))
    return zip_path


def test_month_range_and_build_tables_from_zip(tmp_path: Path):
    assert month_range("2024-11", "2025-02") == [(2024, 11), (2024, 12), (2025, 1), (2025, 2)]
    with pytest.raises(ValueError):
        month_range("2024-05", "2024-01")
    with pytest.raises(ValueError):
        month_range("2024-13", "2024-13")

    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    zip_path = _write_month_zip(raw_dir)

    idx = load_rm_commune_index()
    build_tables_from_zips([zip_path], out_dir, idx, {})
    year_csv = out_dir / "resumen_comuna_anio.csv"
    assert year_csv.exists()
    assert (out_dir / "resumen_sector_comuna.csv").exists()
    assert (out_dir / "manifest.json").exists()
    with year_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    assert "total_reclamos" not in (reader.fieldnames or [])
    assert [r["codigo_comuna"] for r in rows] == ["13201"]

    # Also verify CLI --solo-locales works offline end-to-end.
    out_cli = tmp_path / "out_cli"
    rc = main(
        [
            "--desde",
            "2024-01",
            "--hasta",
            "2024-01",
            "--solo-locales",
            "--raw-dir",
            str(raw_dir),
            "--out-dir",
            str(out_cli),
        ]
    )
    assert rc == 0
    written_manifest = json.loads((out_cli / "manifest.json").read_text(encoding="utf-8"))
    assert written_manifest["diagnosticos"]["filas_resumen_comuna_anio"] == 1


def _run_local(raw_dir: Path, out_dir: Path) -> dict:
    rc = main(
        [
            "--desde", "2024-01", "--hasta", "2024-01", "--solo-locales",
            "--raw-dir", str(raw_dir), "--out-dir", str(out_dir),
        ]
    )
    assert rc == 0
    return json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))


def test_download_date_is_kept_from_manifest_not_file_mtime(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    zip_path = _write_month_zip(raw_dir)
    # Simulate an LFS checkout: the file mtime is the clone date, not the download date.
    clone_ts = dt.datetime(2030, 6, 1, 12, 0).timestamp()
    os.utime(zip_path, (clone_ts, clone_ts))

    # No prior record: the download date is unknown, never the mtime.
    first = _run_local(raw_dir, out_dir)
    (entry,) = first["archivos"].values()
    assert entry["descargado"] is None

    # A prior record with the same sha256 keeps its recorded date.
    sha = entry["sha256"]
    prior = {"archivos": {"otra/ruta/2024-1.zip": {"sha256": sha, "descargado": "2024-02-01"}}}
    (out_dir / "manifest.json").write_text(json.dumps(prior), encoding="utf-8")
    second = _run_local(raw_dir, out_dir)
    (entry2,) = second["archivos"].values()
    assert entry2["descargado"] == "2024-02-01"

    # A prior record with another sha256 is not reused.
    prior_other = {"archivos": {"x.zip": {"sha256": "0" * 64, "descargado": "2024-02-01"}}}
    (out_dir / "manifest.json").write_text(json.dumps(prior_other), encoding="utf-8")
    third = _run_local(raw_dir, out_dir)
    (entry3,) = third["archivos"].values()
    assert entry3["descargado"] is None


def test_genuinely_new_download_records_today(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w") as zf:
        zf.writestr("lic.csv", "CodigoExterno\n")
    payload = body.getvalue()

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        fetch_licitaciones.urllib.request, "urlopen", lambda *a, **k: _Resp(payload)
    )
    path, meta = fetch_licitaciones.download_month_zip(
        2024, 1, tmp_path, delay_s=0, previous_dates={}
    )
    assert path.read_bytes() == payload
    assert meta["descargado"] == dt.date.today().isoformat()

    # Cached file (no new download) with a recorded sha keeps the recorded date.
    sha = meta["sha256"]
    _, cached = fetch_licitaciones.download_month_zip(
        2024, 1, tmp_path, delay_s=0, previous_dates={sha: "2024-02-01"}
    )
    assert cached["descargado"] == "2024-02-01"


def _write_summary_csv(path: Path) -> None:
    """Two years for Santiago: 25 closed and 19 awarded in total, 15 closed in 2024."""
    path.write_text(
        "codigo_comuna,anio,total_licitaciones,adjudicadas,fallidas,cerradas,"
        "tasa_adjudicacion,mediana_dias_pub_cierre,mediana_dias_pub_adj,mediana_oferentes,"
        "proporcion_oferente_unico,monto_estimado_clp,monto_adjudicado_clp\n"
        "13101,2023,11,7,3,10,0.7,9.0,30.0,3.0,0.2,1000.0,800.0\n"
        "13101,2024,16,12,3,15,0.8,8.0,28.0,4.0,0.1,2000.0,1500.0\n",
        encoding="utf-8",
    )


def test_core_licitaciones_loading_and_credibility(tmp_path: Path):
    assert load_procurement_summaries(tmp_path / "missing.csv") == {}

    csv_path = tmp_path / "resumen_comuna_anio.csv"
    _write_summary_csv(csv_path)

    all_years = load_procurement_summaries(csv_path)
    assert all_years["13101"].tenders_closed == 25
    assert all_years["13101"].tenders_awarded == 19
    only_2024 = load_procurement_summaries(csv_path, min_year=2024)
    assert only_2024["13101"].tenders_closed == 15

    # The thresholds are explicit assumptions with their documented values.
    assert MIN_SAMPLE_ASSUMPTION == 20
    assert MAX_EFFECTIVE_N_ASSUMPTION == pytest.approx(40.0)

    prior = BetaCredibility(2.0, 2.0)
    none_est = estimate_commune_credibility(None, prior=prior)
    assert none_est.provenance == "supuesto"
    assert none_est.credibility == prior

    # Below the minimum sample the data is too thin to stand as a base rate.
    small = CommuneProcurementSummary("13102", 8, 6, 2, 8, 100.0, 20.0, 0.2)
    small_est = estimate_commune_credibility(small, prior=prior, min_sample=20)
    assert small_est.provenance == "supuesto"
    assert small_est.credibility.alpha == pytest.approx(8.0)
    assert small_est.credibility.beta == pytest.approx(4.0)

    large = CommuneProcurementSummary("13101", 200, 150, 50, 200, 1000.0, 22.0, 0.1)
    large_est = estimate_commune_credibility(
        large, prior=prior, min_sample=20, max_effective_n=40.0
    )
    # Awarding a tender is not executing a measure: never "medida".
    assert large_est.provenance == "tasa_base"
    assert large_est.effective_sample_size == pytest.approx(40.0)
    assert large_est.credibility.alpha == pytest.approx(2.0 + 30.0)
    assert large_est.credibility.beta == pytest.approx(2.0 + 10.0)
    # The prior shifts the posterior mean away from the observed award rate (0.75).
    assert large_est.award_rate == pytest.approx(0.75)
    assert large_est.credibility.mean == pytest.approx(32.0 / 44.0)
    assert large_est.credibility.mean != pytest.approx(large_est.award_rate)

    for est in (none_est, small_est, large_est):
        assert est.provenance != "medida"
