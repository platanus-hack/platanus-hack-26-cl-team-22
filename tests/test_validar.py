import json

import numpy as np
import pytest

from experiments import validar


def test_rmse_of_known_errors():
    assert validar.rmse(np.array([3.0, -4.0])) == pytest.approx(np.sqrt(12.5))


def test_coverage_counts_values_on_the_band_edges_as_inside():
    observed = np.array([1.0, 2.0, 3.0, 4.0])
    low = np.array([1.0, 0.0, 3.5, 0.0])
    high = np.array([2.0, 1.0, 5.0, 4.0])
    assert validar.coverage(observed, low, high) == pytest.approx(0.5)


def test_linear_trend_extends_an_exact_line():
    years = np.array([2017, 2018, 2019])
    values = np.array([30.0, 28.0, 26.0])
    assert validar.linear_trend(years, values, 2023) == pytest.approx(18.0)


def test_winner_is_the_lowest_error_and_close_errors_tie():
    assert validar.winner({"modelo": 1.0, "sin_cambio": 2.0, "tendencia": None}) == "modelo"
    assert validar.winner({"modelo": 2.0, "sin_cambio": 1.0}) == "sin_cambio"
    assert validar.winner({"modelo": 1.00, "sin_cambio": 1.01}) == "empate"


def test_air_fit_and_test_years_do_not_overlap():
    assert set(validar.AIR_TRAIN_YEARS).isdisjoint(validar.AIR_TEST_YEARS)
    assert set(validar.AIR_ATYPICAL_YEARS).isdisjoint(validar.AIR_TEST_YEARS)
    assert max(validar.AIR_TRAIN_YEARS) == validar.AIR_ORIGIN < min(validar.AIR_TEST_YEARS)


def test_household_fit_and_test_periods_do_not_overlap():
    report = json.loads(validar.HOUSEHOLDS.read_text(encoding="utf-8"))
    fit_end = int(report["ajuste"].split("-")[1])
    test_start = int(report["prueba"].split("-")[0])
    assert fit_end < test_start


@pytest.fixture(scope="module")
def hindcast():
    return validar.air_hindcast(replicas=40)


def test_air_model_without_execution_is_persistence(hindcast):
    # theta = 0: no measure is ever executed, so the engine adds no change to the 2019 level.
    zero = hindcast["lecturas"]["sin-ejecucion"]
    assert zero["rmse_ugm3"] == pytest.approx(hindcast["sin_cambio"]["rmse_ugm3"])


def test_air_hindcast_scores_only_test_years(hindcast):
    assert {p["anio"] for p in hindcast["pares"]} <= set(validar.AIR_TEST_YEARS)
    assert hindcast["n_pares"] == len(hindcast["pares"]) > 0


def test_air_hindcast_is_reproducible(hindcast):
    again = validar.air_hindcast(replicas=40)
    assert again["modelo"] == hindcast["modelo"]


def test_weather_widens_the_band(hindcast):
    model = hindcast["modelo"]
    assert model["ancho_banda_con_clima_ugm3"] > model["ancho_banda_ugm3"]
