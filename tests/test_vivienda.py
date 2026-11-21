"""Housing building permits per RM comuna from MINVU (CECT) yearly table."""

import csv
from pathlib import Path

import pytest

from datos.vivienda.vivienda import leer_permisos

DATA = Path(__file__).resolve().parent.parent / "data" / "vivienda"
CODIGOS = {"Santiago": 13101, "Ñuñoa": 13120}


def _hoja(santiago, nunoa, total=None):
    encabezado = ("Región", "Comuna", 2016, 2017, "2018 (***)", "2024  (*)", "2025 (*)")
    total = total or tuple(a + b for a, b in zip(santiago, nunoa))
    return [
        (None, None, "ESTADÍSTICAS MENSUALES DE EDIFICACIÓN APROBADA"),
        encabezado,
        ("Total País ", None, 999, 999, 999, 999, 999),
        ("Valparaíso", "Valparaíso", 5, 5, 5, 5, 5),
        ("Metropolitana", None, *total),
        ("Metropolitana", "Santiago", *santiago),
        ("Metropolitana", "Ñuñoa", *nunoa),
    ]


def _hojas():
    return {
        "número_total": _hoja((10, 20, 30, 40, 50), (1, 2, 3, 4, 5)),
        "número_departamentos": _hoja((9, 19, 29, 39, 49), (1, 2, 3, 4, 5)),
        "número_casas": _hoja((1, 1, 1, 1, 1), (0, 0, 0, 0, 0)),
        "m2_total": _hoja((700, 1400, 2100, 2800, 3500), (70, 140, 210, 280, 350)),
    }


def test_reads_units_and_area_per_comuna_and_year_ignoring_year_footnotes():
    out = leer_permisos(_hojas(), CODIGOS, [2017, 2018, 2024])
    assert out[(13101, 2018)] == {"viviendas": 30, "departamentos": 29, "casas": 1,
                                  "m2": 2100}
    assert out[(13120, 2024)] == {"viviendas": 4, "departamentos": 4, "casas": 0, "m2": 280}
    assert len(out) == 6


def test_empty_cells_count_as_zero_permits():
    hojas = _hojas()
    hojas["número_casas"] = _hoja((None, None, None, None, None), (0, 0, 0, 0, 0),
                                  total=(0, 0, 0, 0, 0))
    assert leer_permisos(hojas, CODIGOS, [2017])[(13101, 2017)]["casas"] == 0


def test_refuses_a_table_whose_comunas_do_not_add_up_to_the_rm_row():
    hojas = _hojas()
    hojas["número_total"] = _hoja((10, 20, 30, 40, 50), (1, 2, 3, 4, 5),
                                  total=(11, 23, 33, 44, 55))
    with pytest.raises(ValueError, match="RM"):
        leer_permisos(hojas, CODIGOS, [2017])


def test_refuses_a_table_missing_a_comuna():
    hojas = {k: [f for f in v if f[1] != "Ñuñoa"] for k, v in _hojas().items()}
    with pytest.raises(ValueError, match="Ñuñoa"):
        leer_permisos(hojas, CODIGOS, [2017])


# --- published table -------------------------------------------------------------------

def _leer():
    ruta = DATA / "permisos_vivienda.csv"
    if not ruta.exists():
        pytest.skip(f"{ruta} not built yet (run python -m datos.vivienda.fetch_permisos)")
    with ruta.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_every_rm_comuna_has_every_definitive_year_2002_to_2024():
    filas = _leer()
    assert {int(f["anio"]) for f in filas} == set(range(2002, 2025))
    assert len({(f["codigo"], f["anio"]) for f in filas}) == len(filas) == 52 * 23


@pytest.mark.parametrize("anio, total", [(2012, 39_027), (2017, 49_082), (2021, 71_262)])
def test_rm_totals_match_the_minvu_table(anio, total):
    assert sum(int(f["viviendas"]) for f in _leer() if int(f["anio"]) == anio) == total


def test_departments_plus_houses_equal_total_units():
    assert all(int(f["departamentos"]) + int(f["casas"]) == int(f["viviendas"])
               for f in _leer())
