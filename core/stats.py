"""Statistics helpers: time-weighted averages and confidence intervals."""
from __future__ import annotations

import numpy as np
from scipy import stats


class TimeWeighted:
    """Average of a variable that persists over time (queue length, utilization)."""

    def __init__(self, t0: float = 0.0, v0: float = 0.0):
        self.t0, self.t, self.v, self.area = t0, t0, v0, 0.0

    def update(self, t: float, v: float) -> None:
        """Call AFTER changing the state, with the new value."""
        self.area += self.v * (t - self.t)
        self.t, self.v = t, v

    def mean(self, t_end: float) -> float:
        return (self.area + self.v * (t_end - self.t)) / (t_end - self.t0)


def ci(x, conf: float = 0.95) -> tuple[float, float]:
    """Mean and half-width of the t confidence interval. Report as m +/- h."""
    x = np.asarray(x, dtype=float)
    m = x.mean()
    h = stats.t.ppf((1 + conf) / 2, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return float(m), float(h)
