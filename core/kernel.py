"""Discrete-event kernel: event heap + one independent RNG stream per component."""
from __future__ import annotations

import heapq
import itertools
from collections.abc import Callable
from typing import Any

import numpy as np


class Sim:
    def __init__(self, seed: int):
        self.t = 0.0
        self._q: list[tuple[float, int, Callable[..., Any], tuple]] = []
        self._seq = itertools.count()  # stable tie-break for simultaneous events
        self._ss = np.random.SeedSequence(seed)

    def rng(self) -> np.random.Generator:
        """One independent stream per random source; request them in the same order every run."""
        return np.random.default_rng(self._ss.spawn(1)[0])

    def schedule(self, delay: float, fn: Callable[..., Any], *args: Any) -> None:
        if delay < 0:
            raise ValueError("cannot schedule an event in the past")
        heapq.heappush(self._q, (self.t + delay, next(self._seq), fn, args))

    def run(self, until: float) -> None:
        while self._q and self._q[0][0] <= until:
            self.t, _, fn, args = heapq.heappop(self._q)
            fn(*args)
        self.t = until
