"""Reference model: M/M/1 queue. Validates the kernel and serves as a template for the real model."""
from __future__ import annotations

from collections import deque

from core.kernel import Sim
from core.stats import TimeWeighted


def run_mm1(lam: float, mu: float, horizon: float, warmup: float, seed: int) -> dict[str, float]:
    if lam >= mu:
        raise ValueError(f"unstable system: rho={lam / mu:.2f} >= 1 (queue grows without bound)")

    sim = Sim(seed)
    rng_arr, rng_srv = sim.rng(), sim.rng()  # one stream per random source
    queue: deque[float] = deque()
    state = {"busy": False}
    waits: list[float] = []
    in_system = TimeWeighted()

    def count() -> int:
        return len(queue) + (1 if state["busy"] else 0)

    def arrival() -> None:
        sim.schedule(rng_arr.exponential(1 / lam), arrival)
        if state["busy"]:
            queue.append(sim.t)
        else:
            state["busy"] = True
            waits.append(0.0)
            sim.schedule(rng_srv.exponential(1 / mu), departure)
        in_system.update(sim.t, count())

    def departure() -> None:
        if queue:
            waits.append(sim.t - queue.popleft())
            sim.schedule(rng_srv.exponential(1 / mu), departure)
        else:
            state["busy"] = False
        in_system.update(sim.t, count())

    def reset_stats() -> None:
        nonlocal in_system
        waits.clear()
        in_system = TimeWeighted(sim.t, count())

    sim.schedule(rng_arr.exponential(1 / lam), arrival)
    sim.schedule(warmup, reset_stats)
    sim.run(horizon)
    return {"Wq": sum(waits) / len(waits), "L": in_system.mean(horizon)}
