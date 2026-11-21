import numpy as np
import pytest

from core.estado import SOURCES, RegionState


def make_state(**overrides):
    base = {
        "year": 2026,
        "codes": ("a", "b", "c"),
        "pm25": np.array([20.0, 25.0, 30.0]),
        "population": np.array([1000.0, 2000.0, 3000.0]),
        "emissions": np.ones((3, len(SOURCES))),
    }
    base.update(overrides)
    return RegionState(**base)


def test_valid_state_exposes_size_and_total_population():
    s = make_state()
    assert s.n_communes == 3
    assert s.total_population == 6000.0


def test_advance_increments_year_and_carries_over_unchanged_arrays():
    s = make_state()
    nxt = s.advance(pm25=np.array([10.0, 11.0, 12.0]))
    assert nxt.year == 2027
    assert np.array_equal(nxt.pm25, [10.0, 11.0, 12.0])
    assert nxt.population is s.population
    assert nxt.emissions is s.emissions


def test_advance_does_not_mutate_the_original_state():
    s = make_state()
    s.advance(pm25=np.zeros(3))
    assert np.array_equal(s.pm25, [20.0, 25.0, 30.0])
    assert s.year == 2026


@pytest.mark.parametrize(
    "overrides",
    [
        {"codes": ("a", "a", "c")},
        {"pm25": np.array([1.0, 2.0])},
        {"population": np.array([1.0, 2.0])},
        {"emissions": np.ones((3, 2))},
        {"pm25": np.array([1.0, -2.0, 3.0])},
        {"population": np.array([1.0, np.nan, 3.0])},
    ],
)
def test_invalid_state_is_rejected(overrides):
    with pytest.raises(ValueError):
        make_state(**overrides)
