"""Rules that turn INE census data into RM inter-comuna move matrices."""

import csv
from pathlib import Path

import pandas as pd
import pytest

from datos.censo.censo import completar_rm, matriz_2024, pares_2017

DATA = Path(__file__).resolve().parent.parent / "data" / "censo"


def _p17(*filas):
    cols = ["COMUNA", "P10", "P10COMUNA", "P11", "P11COMUNA"]
    return pd.DataFrame(filas, columns=cols)


def _como_dict(df):
    return {(o, d): p for o, d, p in df[["codigo_origen", "codigo_destino", "personas"]]
            .itertuples(index=False)}


# --- 2017: built from microdata --------------------------------------------------------

def test_2017_resident_who_moved_between_rm_comunas_counts_as_one_move():
    out = pares_2017(_p17((13102, 1, 98, 3, 13101)))
    assert _como_dict(out) == {(13101, 13102): 1}


def test_2017_lived_in_this_comuna_five_years_ago_is_a_stayer_on_the_diagonal():
    out = pares_2017(_p17((13101, 2, 98, 2, 98), (13101, 1, 98, 2, 98)))
    assert _como_dict(out) == {(13101, 13101): 2}


def test_2017_destination_is_the_usual_residence_when_counted_elsewhere():
    out = pares_2017(_p17((13101, 3, 13110, 3, 13120)))
    assert _como_dict(out) == {(13120, 13110): 1}


def test_2017_counted_elsewhere_and_this_comuna_five_years_ago_is_dropped():
    # "En esta comuna" points to where they were counted, not where they live.
    out = pares_2017(_p17((13101, 3, 13110, 2, 98)))
    assert out.empty


@pytest.mark.parametrize("fila", [
    (13101, 1, 98, 3, 5101),    # origin outside RM
    (13101, 1, 98, 3, 13000),   # region known, comuna unknown
    (13101, 1, 98, 3, 997),     # comuna not declared
    (13101, 1, 98, 1, 98),      # not born yet
    (13101, 1, 98, 4, 98),      # lived abroad
    (13101, 1, 98, 99, 99),     # missing
    (13101, 4, 98, 3, 13102),   # usual residence abroad
    (13101, 3, 997, 3, 13102),  # usual residence not declared
    (5101, 1, 98, 3, 13101),    # destination outside RM
])
def test_2017_rows_without_two_known_rm_comunas_are_dropped(fila):
    assert pares_2017(_p17(fila)).empty


def test_2017_aggregates_people_per_pair():
    out = pares_2017(_p17(*[(13102, 1, 98, 3, 13101)] * 3))
    assert _como_dict(out) == {(13101, 13102): 3}


# --- 2024: reshaped from the INE table D5, sheet "2" -----------------------------------

def _hoja_d5(nombre_col_rm2="Independencia"):
    encabezado = ("Código región", "Región", "Código provincia", "Provincia", "Código comuna",
                  "Comuna", "Población censada", "No migrante interno comunal",
                  "Aún no nacían (menores de 5 años)", "Arica", "Santiago", nombre_col_rm2,
                  "Residencia habitual hace cinco años fuera del país")
    return [
        ("", None), ("", None), ("2. Población censada ...", None),
        encabezado,
        (0, "País", 0, "País", 0, "País", 999, 900, 50, 1, 2, 3, 4),
        (15, "Arica y P.", 151, "Arica", 15101, "Arica", 100, 90, 5, "-", 1, 0, 4),
        (13, "RM", 131, "Santiago", 13101, "Santiago", 200, 150, 10, 2, "-", 7, 31),
        (13, "RM", 131, "Santiago", 13108, "Independencia", 80, 60, 5, 0, 11, "-", 4),
        (None, None),
    ]


def test_2024_reshapes_rm_rows_and_columns_with_stayers_on_the_diagonal():
    out = matriz_2024(_hoja_d5())
    assert _como_dict(out) == {
        (13101, 13101): 150, (13108, 13101): 7,
        (13101, 13108): 11, (13108, 13108): 60,
    }


def test_2024_refuses_a_sheet_whose_columns_do_not_follow_the_rows():
    with pytest.raises(ValueError, match="Independencia"):
        matriz_2024(_hoja_d5(nombre_col_rm2="Recoleta"))


def test_2024_refuses_a_sheet_with_more_comuna_rows_than_origin_columns():
    hoja = _hoja_d5()
    hoja.insert(-1, (13, "RM", 131, "Santiago", 13110, "La Florida", 5, 5, 0, 0, 0, 0, 0))
    with pytest.raises(ValueError, match="layout changed"):
        matriz_2024(hoja)


def test_2024_refuses_a_sheet_without_its_header_row():
    with pytest.raises(ValueError, match="layout changed"):
        matriz_2024([f for f in _hoja_d5() if f[0] != "Código región"])


# --- shared ----------------------------------------------------------------------------

def test_completar_rm_lists_every_pair_with_zero_when_nobody_moved():
    pares = pd.DataFrame({"codigo_origen": [13101], "codigo_destino": [13102], "personas": [5]})
    out = completar_rm(pares, [13101, 13102])
    assert _como_dict(out) == {(13101, 13101): 0, (13101, 13102): 5,
                               (13102, 13101): 0, (13102, 13102): 0}
    assert list(out.columns) == ["codigo_origen", "codigo_destino", "personas"]


# --- published tables (data/censo) -----------------------------------------------------

def _leer(nombre):
    ruta = DATA / nombre
    if not ruta.exists():
        pytest.skip(f"{ruta} not built yet (run datos/censo/fetch_censo.py)")
    with ruta.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_population_and_dwellings_match_official_rm_totals():
    filas = _leer("poblacion_viviendas.csv")
    por_anio = {}
    for f in filas:
        tot = por_anio.setdefault(f["anio"], {"n": 0, "poblacion": 0, "viviendas": 0})
        tot["n"] += 1
        tot["poblacion"] += int(f["poblacion"])
        tot["viviendas"] += int(f["viviendas"])
    # INE: Censo 2024 RM 7.400.741 personas, 2.764.749 viviendas censadas.
    assert por_anio["2024"] == {"n": 52, "poblacion": 7_400_741, "viviendas": 2_764_749}
    # INE: Censo 2017 residentes habituales por comuna (suma de las 52 comunas).
    # INE (geoarchivos, RM 2017): 2.378.442 viviendas; built from microdata with P01 1-8.
    assert por_anio["2017"] == {"n": 52, "poblacion": 7_028_421, "viviendas": 2_378_442}


@pytest.mark.parametrize("nombre", ["mudanzas_2012_2017.csv", "mudanzas_2019_2024.csv"])
def test_move_matrices_cover_every_rm_pair_once(nombre):
    filas = _leer(nombre)
    codigos = {f["codigo"] for f in _leer("poblacion_viviendas.csv")}
    pares = {(f["codigo_origen"], f["codigo_destino"]) for f in filas}
    assert len(filas) == len(pares) == 52 * 52
    assert {o for o, _ in pares} == codigos
    assert all(int(f["personas"]) >= 0 for f in filas)


@pytest.mark.parametrize("nombre, mudanzas, permanecen", [
    # 2019-2024 off-diagonal total equals the INE table D5; stayers come from its
    # "No migrante interno comunal" column.
    ("mudanzas_2019_2024.csv", 993_528, 5_471_843),
    # 2012-2017 is rebuilt from microdata: pins the P10/P11 recoding (data/censo/README.md).
    ("mudanzas_2012_2017.csv", 910_411, 4_975_480),
])
def test_matrix_control_totals(nombre, mudanzas, permanecen):
    filas = _leer(nombre)
    fuera = sum(int(f["personas"]) for f in filas if f["codigo_origen"] != f["codigo_destino"])
    dentro = sum(int(f["personas"]) for f in filas if f["codigo_origen"] == f["codigo_destino"])
    assert (fuera, dentro) == (mudanzas, permanecen)
