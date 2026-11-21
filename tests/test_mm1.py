"""Kernel validation against queueing theory (mandatory before building the real model)."""
import pytest

from core.mm1 import run_mm1
from experiments.replicate import replicate

LAM, MU = 0.8, 1.0
RHO = LAM / MU
WQ_THEORY = RHO / (MU - LAM)  # 4.0
L_THEORY = RHO / (1 - RHO)    # 4.0


@pytest.fixture(scope="module")
def result():
    return replicate(run_mm1, n=20, lam=LAM, mu=MU, horizon=20000, warmup=1000)


def test_ci_covers_theoretical_wq(result):
    m, h = result["Wq"]
    assert abs(m - WQ_THEORY) <= h * 1.5


def test_ci_covers_theoretical_l(result):
    m, h = result["L"]
    assert abs(m - L_THEORY) <= h * 1.5


def test_littles_law(result):
    # L ~= lambda * (Wq + 1/mu)
    assert result["L"][0] == pytest.approx(LAM * (result["Wq"][0] + 1 / MU), rel=0.05)


def test_reproducible():
    kw = {"lam": LAM, "mu": MU, "horizon": 2000, "warmup": 100}
    assert run_mm1(seed=7, **kw) == run_mm1(seed=7, **kw)


def test_unstable_system_is_rejected():
    with pytest.raises(ValueError):
        run_mm1(lam=1.0, mu=1.0, horizon=100, warmup=0, seed=1)
