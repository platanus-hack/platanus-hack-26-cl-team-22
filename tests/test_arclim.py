import csv
import gzip
import json
from pathlib import Path

import pytest

from datos.arclim.fetch_arclim import COMMUNES, INDICATORS, OUT, SCENARIOS

RM_CODES = {r["codigo_comuna"] for r in csv.DictReader(COMMUNES.open(encoding="utf-8-sig"))}


@pytest.mark.parametrize("indicator", INDICATORS)
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_series_covers_the_52_communes_and_1970_2069(indicator, scenario):
    with gzip.open(OUT / f"series_{indicator}_{scenario}.csv.gz", "rt", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    header, body = rows[0], rows[1:]
    assert [int(y) for y in header[5:]] == list(range(1970, 2070))
    assert {r[0] for r in body} == RM_CODES
    runs = {code: sum(1 for r in body if r[0] == code) for code in RM_CODES}
    assert len(set(runs.values())) == 1 and min(runs.values()) > 0


def test_components_have_one_row_per_rm_commune():
    with (OUT / "componentes_comuna.csv").open(encoding="utf-8") as fh:
        codes = [r["codigo_comuna"] for r in csv.DictReader(fh)]
    assert sorted(codes) == sorted(RM_CODES)


def test_manifest_records_url_date_and_hash_for_every_response():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    files = manifest["archivos"]
    assert len(files) == len(INDICATORS) * len(SCENARIOS) * len(RM_CODES) + 1
    for entry in files.values():
        assert entry["url"].startswith("https://arclim.mma.gob.cl/api/")
        assert len(entry["sha256"]) == 64
        assert entry["descargado"]
    assert all(Path(p).parts[:3] == ("data", "raw", "arclim") for p in files)
