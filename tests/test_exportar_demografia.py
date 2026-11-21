"""Parameters exported for the in-browser household lab (viz/public/datos/demografia.json)."""

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.datos_aire import load_communes
from experiments.datos_hogares import load_population_dwellings
from experiments.exportar_demografia import tasas_recientes

SALIDA = Path(__file__).resolve().parent.parent / "viz" / "public" / "datos" / "demografia.json"


def test_recent_rates_reproduce_the_recent_rm_totals():
    codes = load_communes().codes
    pob24, _ = load_population_dwellings(codes, 2024)
    t = tasas_recientes(codes, pob24)
    # INE yearbooks: births 2022 76.129 and 2023 68.866; deaths 2019 41.866, 2022 49.967,
    # 2023 44.634 (2020-2021 COVID excess left out). Census 2024 external flows / 5.
    assert t.natalidad @ pob24 == pytest.approx((76_129 + 68_866) / 2)
    assert t.mortalidad @ pob24 == pytest.approx((41_866 + 49_967 + 44_634) / 3)
    assert t.llegan_extranjero @ pob24 == pytest.approx(338_266 / 5)
    assert t.salen_regiones @ pob24 == pytest.approx(396_965 / 5)
    assert t.llegan_regiones @ pob24 == pytest.approx(179_275 / 5)


def _export():
    if not SALIDA.exists():
        pytest.skip("run python -m experiments.exportar_demografia")
    return json.loads(SALIDA.read_text(encoding="utf-8"))


def test_export_has_consistent_shapes():
    d = _export()
    n = len(d["comunas"])
    assert n == 52
    assert len(d["poblacion_inicial"]) == len(d["tasa_salida"]) == n
    assert np.shape(d["destinos"]) == (n, n)
    assert all(len(v) == n for v in d["tasas"].values())
    assert np.allclose(np.sum(d["destinos"], axis=1), 1.0)


def test_reference_projections_start_from_the_census_and_closed_keeps_the_total():
    d = _export()
    anios = d["meta"]["anios"]
    for ref in d["referencia"].values():
        assert np.shape(ref["poblacion"]) == (len(anios), 52)
        assert ref["poblacion"][0] == pytest.approx(d["poblacion_inicial"])
    cerrado = np.array(d["referencia"]["cerrado"]["poblacion"])
    assert cerrado.sum(axis=1) == pytest.approx(np.full(len(anios), cerrado[0].sum()))


def test_export_carries_the_agent_simulation_parameters():
    d = _export()
    abm = d["abm"]
    pob = np.array(d["poblacion_inicial"])
    for k in ("capacidad_inicial", "permisos_anuales", "personas_por_vivienda", "stock_extranjero"):
        assert len(abm[k]) == 52, k
    # Capacity counts every census dwelling (vacant included) at the occupied density,
    # so each comuna starts with some room.
    assert np.all(np.array(abm["capacidad_inicial"]) >= pob)
    assert 0 < abm["phi"] < 3
