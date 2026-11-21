import numpy as np
import pytest

from core.aire import AirModel, distance_matrix_km, exponential_transfer
from core.ciclo import Intervention, emission_multipliers, simulate
from core.credibilidad import BetaCredibility, Measure, draw_theta
from core.estado import SOURCES, RegionState

HEATING = SOURCES.index("heating")
INDUSTRY = SOURCES.index("industry")
LAT = np.array([-33.45, -33.45, -33.45])
LON = np.array([-70.65, -70.596, -70.435])
N_YEARS = 12


def state():
    emissions = np.full((3, len(SOURCES)), 100.0)
    return RegionState(2026, ("a", "b", "c"), np.zeros(3), np.full(3, 1000.0), emissions)


def air():
    t = exponential_transfer(distance_matrix_km(LAT, LON), 10.0)
    return AirModel(t, 5.0, np.full(len(SOURCES), 0.01))


def intervention(mid, source="heating", communes=(False, False, True), factor=0.0, years=5):
    measure = Measure(mid, "ppda", BetaCredibility(2.0, 2.0), "supuesto")
    return Intervention(measure, source, np.array(communes), factor, years)


def run(ivs, theta, replica=0, seed=1):
    return simulate(state(), air(), ivs, np.asarray(theta, float), n_years=N_YEARS, seed=seed,
                    replica=replica)


def test_zero_credibility_is_identical_to_no_policy():
    no_policy = run([], [])
    assert np.array_equal(run([intervention("ban")], [0.0]), no_policy)


def test_full_credibility_reaches_the_full_effect_after_the_ramp():
    iv = intervention("ban", communes=(True, True, True), factor=0.0, years=5)
    executed = np.ones((1, N_YEARS), dtype=bool)
    mult = emission_multipliers([iv], executed, 3)
    assert np.allclose(mult[:, 0, HEATING][:5], [0.8, 0.6, 0.4, 0.2, 0.0])
    assert np.allclose(mult[5:, :, HEATING], 0.0)
    assert np.allclose(mult[:, :, INDUSTRY], 1.0)


def test_years_without_execution_deliver_nothing():
    iv = intervention("cut", communes=(True, False, False), factor=0.5, years=2)
    executed = np.array([[False, True, False, True, True]])
    mult = emission_multipliers([iv], executed, 3)[:, 0, HEATING]
    assert np.allclose(mult, [1.0, 0.75, 0.75, 0.5, 0.5])


def test_a_measure_in_one_commune_improves_the_air_of_the_others():
    base = run([], [])
    with_ban = run([intervention("ban", communes=(False, False, True))], [1.0])
    assert np.all(with_ban[-1] < base[-1])  # communes a and b also improve


def test_removing_a_policy_leaves_the_other_policy_unchanged():
    a = intervention("a", communes=(True, False, False))
    b = intervention("b", source="industry", communes=(False, True, False))
    theta = draw_theta([a.measure, b.measure], seed=3, replica=0)
    both = run([a, b], theta, seed=3)
    only_a = run([a], theta[:1], seed=3)
    only_b = run([b], theta[1:], seed=3)
    no_policy = run([], [], seed=3)
    # Effects add exactly in the linear air model when the same draws are kept.
    assert np.allclose(both - no_policy, (only_a - no_policy) + (only_b - no_policy))


def test_same_seed_reproduces_and_other_replica_differs():
    ivs = [intervention("ban")]
    assert np.array_equal(run(ivs, [0.5]), run(ivs, [0.5]))
    assert not np.array_equal(run(ivs, [0.5], replica=0), run(ivs, [0.5], replica=1))


@pytest.mark.parametrize(
    "call",
    [
        lambda: intervention("x", source="ships"),
        lambda: intervention("x", years=0),
        lambda: intervention("x", factor=-0.1),
        lambda: Intervention(intervention("x").measure, "heating", np.ones(3), 0.0, 1),
        lambda: emission_multipliers([intervention("x")], np.ones((1, 2), bool), 4),
    ],
)
def test_invalid_inputs_are_rejected(call):
    with pytest.raises(ValueError):
        call()
