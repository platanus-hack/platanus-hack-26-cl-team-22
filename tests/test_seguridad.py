import numpy as np
import pytest

from core.credibilidad import BetaCredibility, Measure
from core.seguridad import (
    GROUPS,
    CrimeModel,
    EffectSize,
    SecurityIntervention,
    simulate_security,
)

CODES = ("a", "b", "c")
# a and b are neighbors; c is far from both.
NEIGHBORS = np.array([[False, True, False], [True, False, False], [False, False, False]])
EFFECT = EffectSize(1.16, 1.03, 1.27, 0.90)
N_YEARS = 8


def model(phi=0.5, sigma=0.1):
    log_mean = np.log(np.array([[1000.0, 300.0], [800.0, 200.0], [500.0, 100.0]]))
    return CrimeModel(CODES, log_mean, np.full(2, phi), np.full(2, sigma), NEIGHBORS)


def policy(mid, communes, coverage=0.5, years=2):
    measure = Measure(mid, f"municipio-{mid}", BetaCredibility(2.0, 2.0), "supuesto")
    return SecurityIntervention(measure, np.array(communes), coverage,
                                dict.fromkeys(GROUPS, EFFECT), years)


def run(ivs, theta, spillover=(0.0, 0.0), replica=0, m=None):
    m = model() if m is None else m
    return simulate_security(m, m.log_mean.copy(), ivs, np.asarray(theta, float),
                             n_years=N_YEARS, seed=7, replica=replica, spillover=spillover)


def test_zero_credibility_is_identical_to_no_policy():
    assert np.array_equal(run([policy("p", [True, False, False])], [0.0]), run([], []))


def test_full_credibility_lowers_crime_in_the_treated_commune_only_without_spillover():
    base = run([], [])
    treated = run([policy("p", [True, False, False])], [1.0])
    assert np.all(treated[-1, 0] < base[-1, 0])
    assert np.array_equal(treated[:, 1:], base[:, 1:])


@pytest.mark.parametrize(("share", "neighbor_lower"), [(0.5, True), (-0.5, False)])
def test_neighbor_effect_has_an_open_sign_and_spares_far_communes(share, neighbor_lower):
    base = run([], [])
    out = run([policy("p", [True, False, False])], [1.0], spillover=(share, share))
    assert np.all(out[-1, 1] < base[-1, 1]) == neighbor_lower
    assert np.all(out[-1, 1] > base[-1, 1]) == (not neighbor_lower)
    assert np.array_equal(out[:, 2], base[:, 2])  # c is not a neighbor


def test_removing_a_policy_leaves_the_other_commune_unchanged():
    a = policy("a", [True, False, False])
    c = policy("c", [False, False, True])
    both = run([a, c], [1.0, 1.0], spillover=(0.1, 0.1))
    only_c = run([c], [1.0], spillover=(0.1, 0.1))
    assert np.array_equal(both[:, 2], only_c[:, 2])


def test_baseline_is_reproducible_and_reverts_to_the_commune_mean():
    m = model(phi=0.0, sigma=0.0)
    out = run([], [], m=m)
    assert np.allclose(out, np.exp(m.log_mean)[None])
    assert np.array_equal(run([], []), run([], []))
    assert not np.array_equal(run([], [], replica=0), run([], [], replica=1))


def test_drawn_reduction_follows_the_cited_interval():
    draws = np.array([EFFECT.draw_reduction(np.random.default_rng(i)) for i in range(4000)])
    assert np.median(draws) == pytest.approx(1 - 1 / 1.16, abs=0.01)
    inside = np.mean((draws >= 1 - 1 / 1.03) & (draws <= 1 - 1 / 1.27))
    assert inside == pytest.approx(0.90, abs=0.02)


@pytest.mark.parametrize(
    "call",
    [
        lambda: EffectSize(1.2, 1.3, 1.4, 0.95),
        lambda: EffectSize(1.2, 1.1, 1.3, 1.5),
        lambda: policy("x", [True, False, False], coverage=1.5),
        lambda: SecurityIntervention(policy("x", [True, False, False]).measure,
                                     np.array([True, False, False]), 0.5,
                                     {"property": EFFECT}, 2),
        lambda: CrimeModel(CODES, np.zeros((3, 2)), np.full(2, 1.0), np.ones(2), NEIGHBORS),
        lambda: CrimeModel(CODES, np.zeros((3, 2)), np.zeros(2), np.ones(2),
                           np.eye(3, dtype=bool)),
        lambda: run([], [], spillover=(0.2, -0.2)),
    ],
)
def test_invalid_inputs_are_rejected(call):
    with pytest.raises(ValueError):
        call()
