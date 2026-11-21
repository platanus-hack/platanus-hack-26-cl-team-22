import csv
import json

import pytest

from datos.comun import ROOT, clave, comunas_rm, cut_de
from datos.dga.fetch_decretos import communes_in, iso_date

RM = {r["codigo_comuna"] for r in comunas_rm()}
MELIPILLA = sorted(r["codigo_comuna"] for r in comunas_rm() if r["provincia"] == "Melipilla")


def read(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --- Commune names -> CUT ---
def test_name_key_ignores_accents_case_and_spaces():
    assert clave("Til til") == clave("TILTIL") == clave("Tiltil") == "tiltil"
    assert cut_de("Til til") == "13303"
    assert cut_de("ÑUÑOA") == "13120"


def test_names_outside_the_rm_have_no_cut():
    assert cut_de("San Pedro de la Paz") is None


# --- DGA decree text parsing ---
def test_decree_naming_a_commune_covers_only_that_commune():
    assert communes_in("Comuna de Pudahuel, Provincia de Santiago") == (["13124"], False)


def test_decree_naming_only_a_province_covers_all_its_communes():
    assert communes_in("Provincia de Melipilla, Región Metropolitana") == (MELIPILLA, True)


def test_region_name_alone_does_not_count_as_the_commune_of_santiago():
    assert communes_in("Región Metropolitana de Santiago") == ([], False)


def test_decree_dates_are_read_from_spanish_text():
    assert iso_date("N° 178 de 17 de octubre de 2022") == "2022-10-17"
    assert iso_date("sin fecha") == ""


# --- Downloaded tables ---
@pytest.mark.parametrize("path", ["data/dga/decretos_escasez_rm.csv",
                                  "data/sma/procesos_rm.csv",
                                  "data/energia/subestaciones_rm.csv"])
def test_every_row_has_an_rm_cut(path):
    assert {r["codigo_comuna"] for r in read(path)} <= RM


def test_dga_decrees_cover_24_communes_and_drop_mislabelled_rows():
    rows = read("data/dga/decretos_escasez_rm.csv")
    assert len({r["codigo_comuna"] for r in rows}) == 24
    manifest = json.loads((ROOT / "data/dga/manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["filas_rm_descartadas"]) == 2


def test_plants_without_commune_are_kept_with_coordinates():
    rows = read("data/energia/centrales_rm.csv")
    assert {r["codigo_comuna"] for r in rows} <= RM | {""}
    orphans = [r for r in rows if r["codigo_comuna"] == ""]
    assert orphans and all(r["latitud"] and r["longitud"] for r in orphans)


@pytest.mark.parametrize("source", ["dga", "energia", "sma"])
def test_manifest_records_url_date_and_hash(source):
    manifest = json.loads((ROOT / f"data/{source}/manifest.json").read_text(encoding="utf-8"))
    assert manifest["archivos"]
    for entry in manifest["archivos"].values():
        assert entry["url"].startswith("https://")
        assert len(entry["sha256"]) == 64 and entry["descargado"]
