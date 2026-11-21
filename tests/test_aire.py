import numpy as np
import pytest

from core.aire import AirModel, distance_matrix_km, exponential_transfer
from core.estado import SOURCES

N_SOURCES = len(SOURCES)
# Three communes on a line, roughly 0, 5 and 20 km apart (Santiago latitude).
LAT = np.array([-33.45, -33.45, -33.45])
LON = np.array([-70.65, -70.596, -70.435])


def make_model(scale_km=10.0, background=8.0, coefficients=None):
    t = exponential_transfer(distance_matrix_km(LAT, LON), scale_km)
    k = np.full(N_SOURCES, 0.01) if coefficients is None else np.asarray(coefficients, float)
    return AirModel(transfer=t, background=background, coefficients=k)


def emissions_in(commune, source=0, tonnes=100.0):
    e = np.zeros((3, N_SOURCES))
    e[commune, source] = tonnes
    return e


def test_distance_matrix_is_symmetric_with_zero_diagonal():
    d = distance_matrix_km(LAT, LON)
    assert np.allclose(d, d.T)
    assert np.allclose(np.diag(d), 0.0)
    assert d[0, 1] == pytest.approx(5.0, rel=0.05)


def test_distance_between_two_sets_matches_the_pairwise_matrix():
    full = distance_matrix_km(LAT, LON)
    cross = distance_matrix_km(LAT[:1], LON[:1], LAT, LON)
    assert cross.shape == (1, 3)
    assert np.allclose(cross[0], full[0])


def test_transfer_is_one_on_the_diagonal_and_decays_with_distance():
    t = exponential_transfer(distance_matrix_km(LAT, LON), 10.0)
    assert np.allclose(np.diag(t), 1.0)
    assert t[0, 1] > t[0, 2] > 0


def test_zero_emissions_give_background_everywhere():
    m = make_model()
    assert np.allclose(m.concentration(np.zeros((3, N_SOURCES))), 8.0)


def test_emissions_in_one_commune_raise_the_air_of_the_others():
    m = make_model()
    c = m.concentration(emissions_in(0)) - 8.0
    assert c[0] > c[1] > c[2] > 0


def test_superposition_of_emission_sets():
    m = make_model()
    e1, e2 = emissions_in(0, 0), emissions_in(2, 1, 40.0)
    joint = m.concentration(e1 + e2) - 8.0
    assert np.allclose(joint, (m.concentration(e1) - 8.0) + (m.concentration(e2) - 8.0))


def test_with_minus_without_equals_k_times_transfer_of_the_change():
    k = np.array([0.02, 0.01, 0.005, 0.001])
    m = make_model(coefficients=k)
    base = np.full((3, N_SOURCES), 50.0)
    policy = base.copy()
    policy[:, 0] *= 0.5
    delta = m.concentration(policy) - m.concentration(base)
    assert np.allclose(delta, k[0] * m.transfer @ (policy - base)[:, 0])


def test_decompositions_add_up_to_the_concentration():
    m = make_model()
    e = np.abs(np.random.default_rng(0).normal(50, 20, (3, N_SOURCES)))
    c = m.concentration(e)
    assert np.allclose(m.background + m.by_source(e).sum(axis=1), c)
    assert np.allclose(m.background + m.by_origin(e).sum(axis=1), c)


@pytest.mark.parametrize(
    "call",
    [
        lambda: exponential_transfer(np.zeros((2, 2)), 0.0),
        lambda: AirModel(np.ones((2, 3)), 1.0, np.ones(N_SOURCES)),
        lambda: AirModel(np.ones((2, 2)), 1.0, np.ones(N_SOURCES - 1)),
        lambda: AirModel(np.ones((2, 2)), -1.0, np.ones(N_SOURCES)),
        lambda: make_model().concentration(np.zeros((2, N_SOURCES))),
    ],
)
def test_invalid_inputs_are_rejected(call):
    with pytest.raises(ValueError):
        call()
