import numpy as np

from core.stats import TimeWeighted, ci


def test_time_weighted_mean_is_not_the_event_mean():
    tw = TimeWeighted()
    tw.update(1.0, 10)  # value 0 during [0,1)
    tw.update(2.0, 0)   # value 10 during [1,2)
    assert tw.mean(4.0) == 2.5  # (0*1 + 10*1 + 0*2) / 4


def test_ci_covers_known_mean():
    x = np.random.default_rng(0).normal(5, 1, 200)
    m, h = ci(x)
    assert abs(m - 5) < h * 2
