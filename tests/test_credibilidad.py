import numpy as np
import pytest
from scipy import stats

from core.credibilidad import BetaCredibility, Measure, draw_execution, draw_theta

N_YEARS = 20_000


def measure(mid, executor="exec", a=2.0, b=2.0):
    return Measure(mid, executor, BetaCredibility(a, b), "supuesto")


@pytest.mark.parametrize("rho", [0.0, 0.5])
def test_zero_credibility_never_executes_and_full_always_does(rho):
    ms = [measure("a"), measure("b")]
    ex = draw_execution(np.array([0.0, 1.0]), ms, n_years=500, seed=1, replica=0, rho=rho)
    assert not ex[0].any()
    assert ex[1].all()


@pytest.mark.parametrize("rho", [0.0, 0.5])
def test_execution_rate_matches_theta(rho):
    theta = 0.3
    ex = draw_execution(np.array([theta]), [measure("a")], n_years=N_YEARS, seed=2, replica=0,
                        rho=rho)
    tolerance = 4 * np.sqrt(theta * (1 - theta) / N_YEARS)
    assert abs(ex.mean() - theta) < tolerance


def test_shared_executor_correlates_failures_and_different_executors_do_not():
    ms = [measure("a", "muni1"), measure("b", "muni1"), measure("c", "muni2")]
    ex = draw_execution(np.full(3, 0.5), ms, n_years=N_YEARS, seed=3, replica=0, rho=0.5)
    corr = np.corrcoef(ex.astype(float))
    assert corr[0, 1] > 0.2
    assert abs(corr[0, 2]) < 0.05


def test_without_shock_measures_of_same_executor_are_independent():
    ms = [measure("a", "muni1"), measure("b", "muni1")]
    ex = draw_execution(np.full(2, 0.5), ms, n_years=N_YEARS, seed=4, replica=0, rho=0.0)
    assert abs(np.corrcoef(ex.astype(float))[0, 1]) < 0.05


def test_same_seed_reproduces_and_other_replica_differs():
    ms = [measure("a"), measure("b", "other")]
    theta = draw_theta(ms, seed=5, replica=0)
    assert np.array_equal(theta, draw_theta(ms, seed=5, replica=0))
    assert not np.array_equal(theta, draw_theta(ms, seed=5, replica=1))
    ex1 = draw_execution(theta, ms, n_years=50, seed=5, replica=0)
    ex2 = draw_execution(theta, ms, n_years=50, seed=5, replica=0)
    assert np.array_equal(ex1, ex2)


def test_removing_a_measure_leaves_the_others_draws_unchanged():
    a, b = measure("a", "muni1"), measure("b", "muni1")
    theta_ab = draw_theta([a, b], seed=6, replica=0)
    theta_a = draw_theta([a], seed=6, replica=0)
    assert theta_ab[0] == theta_a[0]
    ex_ab = draw_execution(theta_ab, [a, b], n_years=200, seed=6, replica=0)
    ex_a = draw_execution(theta_a, [a], n_years=200, seed=6, replica=0)
    assert np.array_equal(ex_ab[0], ex_a[0])


def test_measure_order_does_not_change_draws():
    a, b = measure("a"), measure("b", "other")
    t_ab = draw_theta([a, b], seed=7, replica=0)
    t_ba = draw_theta([b, a], seed=7, replica=0)
    assert np.array_equal(t_ab, t_ba[::-1])


def thetas_over_replicas(ms, replicas=3000, **kwargs):
    return np.array([draw_theta(ms, seed=8, replica=r, **kwargs) for r in range(replicas)])


@pytest.mark.parametrize("rho_theta", [0.0, 0.5])
def test_theta_keeps_its_beta_marginal(rho_theta):
    ms = [measure("a", "muni1", a=8.0, b=2.0), measure("b", "muni1", a=8.0, b=2.0)]
    theta = thetas_over_replicas(ms, rho_theta=rho_theta)[:, 0]
    assert stats.kstest(theta, stats.beta(8.0, 2.0).cdf).pvalue > 0.01


def test_credibility_is_shared_within_an_executor_only():
    ms = [measure("a", "muni1"), measure("b", "muni1"), measure("c", "muni2")]
    shared = np.corrcoef(thetas_over_replicas(ms, rho_theta=0.5).T)
    assert shared[0, 1] > 0.3
    assert abs(shared[0, 2]) < 0.06
    independent = np.corrcoef(thetas_over_replicas(ms, rho_theta=0.0).T)
    assert abs(independent[0, 1]) < 0.06


def test_beta_binomial_update_and_summary():
    post = BetaCredibility(2.0, 2.0).update(fulfilled=3, total=4)
    assert (post.alpha, post.beta) == (5.0, 3.0)
    s = post.summary()
    assert s["media"] == pytest.approx(5 / 8)
    assert s["p10"] < s["media"] < s["p90"]


def test_more_history_narrows_the_band():
    prior = BetaCredibility(1.0, 1.0)
    few = prior.update(2, 4).summary()
    many = prior.update(50, 100).summary()
    assert many["p90"] - many["p10"] < few["p90"] - few["p10"]


@pytest.mark.parametrize(
    "call",
    [
        lambda: BetaCredibility(0.0, 1.0),
        lambda: BetaCredibility(1.0, 1.0).update(5, 4),
        lambda: BetaCredibility(1.0, 1.0).update(-1, 4),
        lambda: draw_execution(np.array([1.5]), [measure("a")], n_years=1, seed=0, replica=0),
        lambda: draw_execution(np.array([0.5]), [measure("a")], n_years=1, seed=0, replica=0,
                               rho=1.0),
        lambda: draw_execution(np.array([0.5, 0.5]), [measure("a")], n_years=1, seed=0,
                               replica=0),
        lambda: draw_theta([measure("a"), measure("a")], seed=0, replica=0),
        lambda: draw_theta([measure("a")], seed=0, replica=0, rho_theta=1.0),
    ],
)
def test_invalid_inputs_are_rejected(call):
    with pytest.raises(ValueError):
        call()
