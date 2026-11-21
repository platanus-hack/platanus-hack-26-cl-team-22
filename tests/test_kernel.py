import pytest

from core.kernel import Sim


def test_events_run_in_time_order_with_stable_ties():
    sim, log = Sim(1), []
    sim.schedule(2.0, log.append, "c")
    sim.schedule(1.0, log.append, "a")
    sim.schedule(1.0, log.append, "b")  # same time as "a": insertion order wins
    sim.run(10)
    assert log == ["a", "b", "c"]


def test_clock_jumps_to_horizon():
    sim = Sim(1)
    sim.run(5.0)
    assert sim.t == 5.0


def test_past_events_rejected():
    with pytest.raises(ValueError):
        Sim(1).schedule(-1.0, print)


def test_rng_streams_reproducible_and_independent():
    a1, a2 = Sim(7).rng(), Sim(7).rng()
    assert a1.random() == a2.random()
    sim = Sim(7)
    assert sim.rng().random() != sim.rng().random()
