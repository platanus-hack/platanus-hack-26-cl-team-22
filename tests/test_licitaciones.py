"""Tests for ChileCompra ingestion, schema parsing, and procurement credibility."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from core.credibilidad import BetaCredibility
from core.licitaciones import (
    CommuneProcurementSummary,
    estimate_commune_credibility,
    load_procurement_summaries,
)
from datos.licitaciones.enriquecer_ficha import parse_licitalab_payload
from datos.licitaciones.esquema import (
    aggregate_records,
    classify_sector,
    iter_records_from_csv_stream,
    load_rm_commune_index,
    match_rm_commune,
    parse_chilecompra_date,
    parse_chilecompra_float,
)
from datos.licitaciones.fetch_licitaciones import build_tables_from_zips, main, month_range


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


def test_rm_commune_matching_is_conservative():
    idx = load_rm_commune_index()
    assert len(idx) == 52
    assert match_rm_commune("El Bosque", "Cualquier Servicio", idx) == "13105"
    assert match_rm_commune("", "Ilustre Municipalidad de Puente Alto", idx) == "13201"
    assert match_rm_commune("", "I. Municipalidad de Maipú", idx) == "13119"
    assert match_rm_commune("Til Til", "DIRECCION SALUD RURAL", idx) == "13303"
    assert match_rm_commune("", "I MUNICIPALIDAD DE TIL TIL", idx) == "13303"
    # National ministries without RM commune must stay unmatched rather than guessing 13101.
    assert match_rm_commune("", "Ministerio de Obras Públicas", idx) is None
    assert match_rm_commune("Valparaíso", "Municipalidad de Valparaíso", idx) is None


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
        "Muni El Bosque;8;Adjudicada;2024-03-01;2024-03-11;2024-03-21;5000000;2000000;3;1"
    )
    line2 = (
        "100-1-LE24;Recambio estufas;Instalación pellet;Servicio;El Bosque;"
        "Muni El Bosque;8;Adjudicada;2024-03-01;2024-03-11;2024-03-21;5000000;2500000;3;1"
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
    assert row.total_reclamos == 1
    assert {s.sector for s in sector_rows} == {"aire_calefaccion", "seguridad"}


def test_month_range_and_build_tables_from_zip(tmp_path: Path):
    assert month_range("2024-11", "2025-02") == [(2024, 11), (2024, 12), (2025, 1), (2025, 2)]
    with pytest.raises(ValueError):
        month_range("2024-05", "2024-01")
    with pytest.raises(ValueError):
        month_range("2024-13", "2024-13")

    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    raw_dir.mkdir()
    zip_path = raw_dir / "2024-1.zip"
    csv_body = (
        "CodigoExterno;Nombre;Descripcion;ComunaUnidad;NombreOrganismo;"
        "CodigoEstado;FechaPublicacion;FechaCierre;FechaAdjudicacion;"
        "MontoEstimado;MontoLineaAdjudica;NumeroOferentes;CantidadReclamos\n"
        "200-1-LE24;Agua potable;Red hídrica;Puente Alto;Muni;8;"
        "2024-01-05;2024-01-15;2024-01-25;3000000;2800000;4;0\n"
    )
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("lic_2024-1.csv", csv_body.encode("latin-1"))

    idx = load_rm_commune_index()
    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    manifest = build_tables_from_zips(
        [zip_path],
        out_dir,
        idx,
        {"2024-1.zip": {"url": "https://example.invalid/2024-1.zip", "sha256": sha}},
    )
    assert manifest["archivos"]["2024-1.zip"]["sha256"] == sha
    assert (out_dir / "resumen_comuna_anio.csv").exists()
    assert (out_dir / "resumen_sector_comuna.csv").exists()
    assert (out_dir / "manifest.json").exists()

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


def test_parse_licitalab_payload():
    detail = parse_licitalab_payload(
        {
            "tenderId": "3704-39-LE25",
            "name": "Luminarias LED",
            "description": "Recambio de luminarias",
            "status": "Adjudicada",
            "statusCode": 8,
            "TenderDate": {"publish": "2025-01-10T00:00:00", "close": "2025-01-20T00:00:00"},
            "TenderEvaluationCriteria": [{"item_name": "Precio"}],
            "TenderGuarantees": [],
            "tenderPurchaseData": {
                "organization": {"name": "Municipalidad de Santiago", "tax_number": "69.070.100-1"},
                "orgUnit": {"name": "SECPLA", "city": "Santiago", "region": "RM"},
            },
        }
    )
    assert detail.tender_id == "3704-39-LE25"
    assert detail.status_code == 8
    assert detail.criteria_count == 1
    assert detail.guarantees_count == 0
    assert detail.organization_name == "Municipalidad de Santiago"


def test_core_licitaciones_loading_and_credibility(tmp_path: Path):
    assert load_procurement_summaries(tmp_path / "missing.csv") == {}

    csv_path = tmp_path / "resumen_comuna_anio.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
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
                "total_reclamos",
            ]
        )
        w.writerow(["13101", 2023, 10, 7, 3, 10, 0.7, 10, 25, 3, 0.2, 1000, 900, 0])
        w.writerow(["13101", 2024, 15, 12, 3, 15, 0.8, 12, 30, 4, 0.1, 2000, 1800, 1])

    all_years = load_procurement_summaries(csv_path)
    assert all_years["13101"].tenders_closed == 25
    assert all_years["13101"].tenders_awarded == 19
    only_2024 = load_procurement_summaries(csv_path, min_year=2024)
    assert only_2024["13101"].tenders_closed == 15

    prior = BetaCredibility(2.0, 2.0)
    none_est = estimate_commune_credibility(None, prior=prior)
    assert none_est.provenance == "supuesto"
    assert none_est.credibility == prior

    small = CommuneProcurementSummary("13102", 8, 6, 2, 8, 100.0, 20.0, 0.2, 0)
    small_est = estimate_commune_credibility(small, prior=prior, min_sample=20)
    assert small_est.provenance == "tasa_base"
    assert small_est.credibility.alpha == pytest.approx(8.0)
    assert small_est.credibility.beta == pytest.approx(4.0)

    large = CommuneProcurementSummary("13101", 200, 150, 50, 200, 1000.0, 22.0, 0.1, 0)
    large_est = estimate_commune_credibility(
        large, prior=prior, min_sample=20, max_effective_n=40.0
    )
    assert large_est.provenance == "medida"
    assert large_est.effective_sample_size == pytest.approx(40.0)
    assert large_est.credibility.alpha == pytest.approx(2.0 + 30.0)
    assert large_est.credibility.beta == pytest.approx(2.0 + 10.0)
