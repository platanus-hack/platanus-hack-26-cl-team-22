import numpy as np
import pytest

from core.clima import Series, change, common_runs, draw_run, simulate_climate

YEARS = np.arange(1970, 2070)


def test_constant_series_has_no_change():
    values = np.full((2, len(YEARS)), 300.0)
    for kind in ("rel", "abs"):
        out = change(values, YEARS, kind, [2030, 2050])
        assert np.allclose(out, 0.0)


def test_change_uses_the_20_year_window_against_1991_2020():
    values = np.where(YEARS >= 2041, 110.0, 100.0)[None, :]
    # window for 2051 is 2041..2060: every year is 110 -> +10 % and +10 units
    assert change(values, YEARS, "rel", [2051])[0, 0] == pytest.approx(10.0)
    assert change(values, YEARS, "abs", [2051])[0, 0] == pytest.approx(10.0)
    # window for 2041 is 2031..2050: half at 100, half at 110 -> +5 %
    assert change(values, YEARS, "rel", [2041])[0, 0] == pytest.approx(5.0)


def test_change_refuses_years_without_a_full_window():
    values = np.ones((1, len(YEARS)))
    with pytest.raises(ValueError):
        change(values, YEARS, "abs", [2061])  # window 2051..2070, data ends 2069
    change(values, YEARS, "abs", [2060])  # window 2050..2069 is complete


def series(runs):
    return Series(runs=runs, communes=["13101"], years=YEARS,
                  values=np.zeros((len(runs), 1, len(YEARS))))


def test_common_runs_keeps_only_runs_present_in_every_indicator():
    a = series([("G1", "r1"), ("G1", "r2"), ("G2", "r1")])
    b = series([("G2", "r1"), ("G1", "r2"), ("G3", "r1")])
    assert common_runs([a, b]) == [("G1", "r2"), ("G2", "r1")]


def test_draw_run_is_reproducible_and_independent_of_list_order():
    runs = [("G1", "r1"), ("G1", "r2"), ("G2", "r1"), ("G3", "r1")]
    first = [draw_run(runs, seed=22, replica=r) for r in range(50)]
    again = [draw_run(list(reversed(runs)), seed=22, replica=r) for r in range(50)]
    assert first == again


def test_draw_run_picks_each_climate_model_equally_often():
    # G1 has three runs, G2 one: a run-uniform draw would favour G1 3 to 1
    runs = [("G1", "r1"), ("G1", "r2"), ("G1", "r3"), ("G2", "r1")]
    n = 4000
    g1 = sum(draw_run(runs, seed=5, replica=r)[0] == "G1" for r in range(n))
    assert abs(g1 / n - 0.5) < 4 * np.sqrt(0.25 / n)


@pytest.fixture(scope="module")
def real():
    return simulate_climate("ssp245", seed=22, replicas=60, years=[2030, 2051])


def test_real_data_every_drawn_run_carries_all_indicators(real):
    assert len(real["corridas"]) == 60
    assert set(real["corridas"]) <= set(real["corridas_disponibles"])
    assert len(real["corridas_disponibles"]) >= 15


def test_real_data_santiago_warms_by_mid_century(real):
    hot = real["riesgos"]["calor"]["hot_days"]
    assert hot["unidad"] == "días"
    santiago = hot["por_comuna"]["13101"]
    # ARClim ensemble: 71.0 -> 107.6 hot days (1991-2020 -> 2041-2060)
    assert 20 < santiago["p50"][1] < 55
    assert santiago["p10"][1] <= santiago["p50"][1] <= santiago["p90"][1]


def test_real_data_covers_all_communes_and_three_risks(real):
    assert set(real["riesgos"]) == {"hidrico", "inundacion", "calor"}
    for risk in real["riesgos"].values():
        for component in risk.values():
            assert len(component["por_comuna"]) == 52
