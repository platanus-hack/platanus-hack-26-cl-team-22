"""Tests for spatial-temporal map transformation descriptors and simulacion.json integration."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from core.transformaciones import compute_scenario_transformation, serialize_transformations

ROOT = Path(__file__).resolve().parents[1]


def test_compute_scenario_transformation_focus_epicenter_and_directions():
    # Shape: (replicas=3, years=3, communes=3)
    ref = np.zeros((3, 3, 3))
    act = np.zeros((3, 3, 3))
    # Commune 0: large improvement (-4 in final year when better='menor')
    act[:, :, 0] = np.array([[-1.0, -2.0, -4.0], [-1.0, -2.0, -4.0], [-1.0, -2.0, -4.0]])
    # Commune 1: smaller worsening (+1 in final year when better='menor')
    act[:, :, 1] = np.array([[0.2, 0.5, 1.0], [0.2, 0.6, 1.2], [0.2, 0.4, 0.8]])
    # Commune 2: negligible change (filtered out by min_intensity=0.05)
    act[:, :, 2] = 0.01

    codes = ["13101", "13105", "13201"]
    lat = np.array([-33.45, -33.57, -33.62])
    lon = np.array([-70.66, -70.67, -70.58])

    tr = compute_scenario_transformation(
        "con-medida",
        "base",
        "pm25_anual",
        "reduccion_emisiones",
        "menor",
        act,
        ref,
        codes,
        lat,
        lon,
        min_intensity=0.05,
    )

    assert tr.max_abs_delta == pytest.approx(4.0)
    assert [c.codigo for c in tr.comunas_foco] == ["13101", "13105"]
    assert tr.comunas_foco[0].direccion == "mejora"
    assert tr.comunas_foco[1].direccion == "empeora"
    assert tr.comunas_foco[0].intensidad == pytest.approx((0.25, 0.5, 1.0))
    assert tr.comunas_foco[1].incertidumbre[-1] > 0.0
    assert all(0.0 <= v <= 1.0 for v in tr.intensidad_regional)
    # Epicenter must lean strongly toward commune 0 (-33.45).
    assert abs(tr.epicentro_lat - (-33.45)) < abs(tr.epicentro_lat - (-33.57))
    assert tr.bbox == (-70.67, -33.57, -70.66, -33.45)

    # Flip better='mayor': negative delta becomes 'empeora', positive becomes 'mejora'.
    tr_mayor = compute_scenario_transformation(
        "con-medida",
        "base",
        "crecimiento_poblacion",
        "acople_hogares",
        "mayor",
        act,
        ref,
        codes,
        lat,
        lon,
    )
    assert tr_mayor.comunas_foco[0].direccion == "empeora"
    assert tr_mayor.comunas_foco[1].direccion == "mejora"


def test_zero_delta_transformation_has_empty_focus_and_zero_intensity():
    arr = np.ones((2, 4, 2)) * 15.0
    tr = compute_scenario_transformation(
        "sin-cambio",
        "base",
        "pm25_anual",
        "reduccion_emisiones",
        "menor",
        arr,
        arr,
        ["13101", "13102"],
        np.array([-33.45, -33.48]),
        np.array([-70.66, -70.70]),
    )
    assert tr.max_abs_delta == 0.0
    assert tr.comunas_foco == ()
    assert tr.intensidad_regional == (0.0, 0.0, 0.0, 0.0)

    payload = serialize_transformations([tr])
    assert payload["referencia_por_defecto"] == "base"
    assert payload["por_escenario"]["sin-cambio"]["comunas_foco"] == []


def test_simulacion_json_contains_valid_transformaciones_and_existing_keys():
    sim_path = ROOT / "viz" / "datos" / "simulacion.json"
    data = json.loads(sim_path.read_text(encoding="utf-8"))

    for key in (
        "meta",
        "variables",
        "comunas",
        "tipos_hogar",
        "politicas",
        "escenarios",
        "trayectorias",
        "aportes",
        "flujos",
        "impacto",
        "validacion",
        "promesas",
        "migracion_neta",
        "transformaciones",
    ):
        assert key in data, f"Missing key {key!r} in simulacion.json"

    assert "licitaciones" in data["meta"]
    assert set(data["meta"]["licitaciones"]) >= {"disponible", "comunas_con_datos", "comando"}

    n_years = len(data["meta"]["anios"])
    scenario_ids = {s["id"] for s in data["escenarios"]}
    por_esc = data["transformaciones"]["por_escenario"]
    assert set(por_esc) == scenario_ids

    for sid, tr in por_esc.items():
        assert len(tr["intensidad_regional"]) == n_years, sid
        assert all(0.0 <= x <= 1.0 for x in tr["intensidad_regional"]), sid
        assert len(tr["bbox"]) == 4
        for c in tr["comunas_foco"]:
            assert len(c["delta_p50"]) == n_years
            assert len(c["incertidumbre"]) == n_years
            assert len(c["intensidad"]) == n_years
            assert all(0.0 <= x <= 1.0 for x in c["intensidad"])
