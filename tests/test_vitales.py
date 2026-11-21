"""Births and deaths per RM comuna from the INE vital statistics yearbooks (sheet 122-04)."""

import csv
from pathlib import Path

import pytest

from datos.vitales.vitales import leer_anuario

DATA = Path(__file__).resolve().parent.parent / "data" / "vitales"
CODIGOS = {"Santiago": 13101, "Cerrillos": 13102, "Talagante": 13601, "Til Til": 13603}


def _formato_antiguo():
    """2012-2020 layout: one column per concept."""
    return [
        ("1.2.2-04 NACIDOS VIVOS ...",),
        ("", "", "", "DEFUNCIONES", None),
        ("REGIÓN, PROVINCIA Y", "Nacidos Vivos", "Matrimonios", "Generales", "Menores de 1 año"),
        ("COMUNA DE RESIDENCIA", "", "", "", "Def Menor28"),
        ("TOTAL", 999, 50, 888, 7),
        ("VALPARAÍSO", 100, 5, 80, 1),
        ("Valparaíso", 100, 5, 80, 1),
        ("METROPOLITANA", 60, 9, 26, 2),
        ("Provincia Santiago", 40, 6, 20, 1),
        ("Santiago", 30, 4, 15, 1),
        ("Cerrillos", 10, 2, 5, 0),
        ("Talagante", 20, 3, 6, 1),
        ("Talagante", 15, 2, 4, 1),
        ("Tiltil", 5, 1, 2, 0),
        ("LIBERTADOR GENERAL BERNARDO O'HIGGINS", 70, 7, 30, 1),
        ("Santiago", 999, 9, 999, 9),
    ]


def _formato_por_sexo():
    """2021-2023 layout: births and deaths split by sex."""
    return [
        ("1.2.2-04:", "NACIDOS VIVOS, DEFUNCIONES ..."),
        ("REGIÓN, PROVINCIA Y", "Nacidos Vivos", None, None, "Defunciones Generales", None, None),
        ("COMUNA DE RESIDENCIA", "Hombre", "Mujer", "Indeterminado", "Hombre", "Mujer",
         "Indeterminado"),
        ("TOTAL PAIS", 500, 499, 1, 400, 399, 1),
        ("METROPOLITANA", 31, 28, 1, 14, 12, 0),
        ("  Santiago", 20, 19, 1, 10, 10, 0),
        ("Santiago", 15, 14, 1, 8, 7, 0),
        ("Cerrillos", 5, 5, 0, 2, 3, 0),
        ("  Talagante", 11, 9, 0, 4, 2, 0),
        ("Talagante", 8, 7, 0, 3, 1, 0),
        ("Til Til", 3, 2, 0, 1, 1, 0),
    ]


def test_reads_births_and_deaths_per_comuna_in_the_old_layout():
    assert leer_anuario(_formato_antiguo(), CODIGOS) == {
        13101: (30, 15), 13102: (10, 5), 13601: (15, 4), 13603: (5, 2)}


def test_sums_sexes_in_the_new_layout():
    assert leer_anuario(_formato_por_sexo(), CODIGOS) == {
        13101: (30, 15), 13102: (10, 5), 13601: (15, 4), 13603: (5, 2)}


def test_reads_deaths_whose_header_sits_one_row_below_births():
    """2015, 2019 and 2020: 'Generales' is on the row under 'Nacidos vivos'."""
    filas = _formato_antiguo()
    filas[2] = ("REGIÓN, PROVINCIA Y", "Nacidos vivos", "Matrimonios", None, "Menores de 1 año")
    filas[3] = ("COMUNA DE RESIDENCIA", "", "", "Generales", "Def Menor28")
    assert leer_anuario(filas, CODIGOS) == {
        13101: (30, 15), 13102: (10, 5), 13601: (15, 4), 13603: (5, 2)}


def test_refuses_a_sheet_whose_comunas_do_not_add_up_to_the_rm_total():
    filas = _formato_antiguo()
    filas[7] = ("METROPOLITANA", 61, 9, 26, 2)
    with pytest.raises(ValueError, match="RM total"):
        leer_anuario(filas, CODIGOS)


def test_refuses_a_sheet_missing_a_comuna():
    filas = [f for f in _formato_antiguo() if f[0] != "Cerrillos"]
    with pytest.raises(ValueError, match="Cerrillos"):
        leer_anuario(filas, CODIGOS)


# --- published table -------------------------------------------------------------------

def _leer():
    ruta = DATA / "nacimientos_defunciones.csv"
    if not ruta.exists():
        pytest.skip(f"{ruta} not built yet (run python -m datos.vitales.fetch_vitales)")
    with ruta.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_every_rm_comuna_has_every_year_2012_to_2023():
    filas = _leer()
    assert {int(f["anio"]) for f in filas} == set(range(2012, 2024))
    assert len(filas) == 52 * 12
    assert len({(f["codigo"], f["anio"]) for f in filas}) == 52 * 12


@pytest.mark.parametrize("anio, nacimientos, defunciones", [
    # INE yearbook RM totals (sheet 122-04), cross-checked with DEIS microdata.
    (2012, 99_488, 37_286),
    (2017, 92_727, 40_383),
    (2023, 68_866, 44_634),
])
def test_rm_totals_match_the_ine_yearbook(anio, nacimientos, defunciones):
    filas = [f for f in _leer() if int(f["anio"]) == anio]
    assert (sum(int(f["nacimientos"]) for f in filas),
            sum(int(f["defunciones"]) for f in filas)) == (nacimientos, defunciones)
