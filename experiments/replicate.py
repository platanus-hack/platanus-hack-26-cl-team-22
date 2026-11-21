"""Independent replications with confidence intervals -> results/mm1.csv."""
from __future__ import annotations

import csv
from pathlib import Path

from core.mm1 import run_mm1
from core.stats import ci


def replicate(fn, n: int = 20, **params) -> dict[str, tuple[float, float]]:
    """Run fn(seed=i, **params) for i in range(n); return {metric: (mean, half_width)}."""
    runs = [fn(seed=i, **params) for i in range(n)]
    return {k: ci([r[k] for r in runs]) for k in runs[0]}


if __name__ == "__main__":
    out = Path("results")
    out.mkdir(exist_ok=True)
    res = replicate(run_mm1, n=20, lam=0.8, mu=1.0, horizon=20000, warmup=1000)
    with open(out / "mm1.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "mean", "half_width"])
        for k, (m, h) in res.items():
            w.writerow([k, f"{m:.4f}", f"{h:.4f}"])
            print(f"{k} = {m:.2f} +/- {h:.2f}")
