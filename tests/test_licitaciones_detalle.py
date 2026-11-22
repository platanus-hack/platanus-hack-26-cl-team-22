"""Per-tender detail CSV (data/licitaciones/licitaciones_detalle.csv) written by the pipeline."""
from __future__ import annotations

import csv
import zipfile
from collections import Counter
from pathlib import Path

from datos.licitaciones.fetch_licitaciones import DETAIL_CSV_NAME, main

HEADER = (
    "CodigoExterno;Nombre;Descripcion;NombreOrganismo;CodigoEstado;Estado;FechaPublicacion;"
    "FechaCierre;FechaAdjudicacion;MontoEstimado;MontoLineaAdjudica;NumeroOferentes"
)
ROWS = [
    # Awarded tender with two line items: one detail row, line amounts summed.
    ("A-1;Recambio estufas;Calefaccion pellet;Municipalidad de Maipú;8;Adjudicada;2024-03-01;"
    "2024-03-11;2024-03-21;5000000;2000000;3"),
    ("A-1;Recambio estufas;Instalacion;Municipalidad de Maipú;8;Adjudicada;2024-03-01;"
    "2024-03-11;2024-03-21;5000000;2500000;3"),
    # Same code reported once as failed and once as awarded: awarded wins, like the aggregates.
    ("A-2;Camaras de vigilancia;Seguridad;Municipalidad de Maipú;7;Desierta;2024-04-01;"
    "2024-04-06;;1000000;;1"),
    ("A-2;Camaras de vigilancia;Seguridad;Municipalidad de Maipú;8;Adjudicada;2024-04-01;"
    "2024-04-06;2024-04-20;1000000;900000;2"),
    # Failed tender.
    ("A-3;Pavimentacion calle;Obra;I. Municipalidad de Maipú;7;Desierta;2024-05-01;"
    "2024-05-10;;7000000;;0"),
    # Closed but unresolved (code 6): counts in total, not in closed.
    ("A-4;Servicio de aseo;Aseo;Municipalidad de Maipú;6;Cerrada;2024-06-01;2024-06-10;;"
    "300000;;"),
    # Another commune; a non-municipal buyer is left out.
    ("B-1;Agua potable rural;Red;Municipalidad de Puente Alto;9;Adjudicada;2024-01-05;"
    "2024-01-15;2024-01-25;3000000;2800000;4"),
    ("C-1;Servicio nacional;Otro;Subsecretaria General;8;Adjudicada;2024-01-05;2024-01-15;"
    "2024-01-25;3000000;2800000;4"),
]


def _write_zip(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    body = "\n".join([HEADER, *ROWS]) + "\n"
    with zipfile.ZipFile(raw_dir / "2024-1.zip", "w") as zf:
        zf.writestr("lic_2024-1.csv", body.encode("latin-1"))


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _build(tmp_path: Path) -> Path:
    raw_dir, out_dir = tmp_path / "raw", tmp_path / "out"
    _write_zip(raw_dir)
    rc = main(["--desde", "2024-01", "--hasta", "2024-01", "--solo-locales",
               "--raw-dir", str(raw_dir), "--out-dir", str(out_dir)])
    assert rc == 0
    return out_dir


def test_detail_has_one_row_per_deduplicated_tender_with_its_name(tmp_path: Path):
    out_dir = _build(tmp_path)
    rows = _read(out_dir / DETAIL_CSV_NAME)

    assert [(r["codigo_comuna"], r["codigo_externo"]) for r in rows] == [
        ("13119", "A-1"), ("13119", "A-2"), ("13119", "A-3"), ("13119", "A-4"),
        ("13201", "B-1"),
    ]
    by_code = {r["codigo_externo"]: r for r in rows}
    assert by_code["A-1"]["nombre"] == "Recambio estufas"
    assert [by_code[c]["estado"] for c in ("A-1", "A-2", "A-3", "A-4", "B-1")] == [
        "adjudicada", "adjudicada", "fallida", "abierta", "adjudicada"]
    assert by_code["A-4"]["estado_chilecompra"] == "cerrada"
    assert by_code["A-1"]["sector"] == "aire_calefaccion"
    assert float(by_code["A-1"]["monto_estimado_clp"]) == 5_000_000.0
    assert float(by_code["A-1"]["monto_adjudicado_clp"]) == 4_500_000.0
    # No awarded line amount at all: empty, not a made-up 0.
    assert by_code["A-3"]["monto_adjudicado_clp"] == ""
    assert by_code["A-3"]["numero_oferentes"] == "0"
    assert by_code["A-4"]["numero_oferentes"] == ""
    assert by_code["A-1"]["anio"] == "2024"


def test_detail_counts_match_the_commune_year_aggregates_exactly(tmp_path: Path):
    out_dir = _build(tmp_path)
    detail = _read(out_dir / DETAIL_CSV_NAME)
    counts: Counter[tuple[str, str, str]] = Counter()
    for r in detail:
        key = (r["codigo_comuna"], r["anio"])
        counts[(*key, "total_licitaciones")] += 1
        if r["estado"] in ("adjudicada", "fallida"):
            counts[(*key, r["estado"] + "s")] += 1
            counts[(*key, "cerradas")] += 1

    summary = _read(out_dir / "resumen_comuna_anio.csv")
    assert summary  # the aggregates are still written
    for row in summary:
        key = (row["codigo_comuna"], row["anio"])
        for field in ("total_licitaciones", "adjudicadas", "fallidas", "cerradas"):
            assert counts[(*key, field)] == int(row[field]), (key, field)
