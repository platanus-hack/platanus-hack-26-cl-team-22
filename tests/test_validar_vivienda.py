"""Destination models for household moves: gravity with housing, pivot and radiation."""

import numpy as np
import pytest

from experiments.validar_vivienda import (
    ajustar_destinos,
    pivote_por_permisos,
    radiacion,
    shares_destinos,
)


def _caracteristicas(n=6, seed=0):
    rng = np.random.default_rng(seed)
    dist = rng.uniform(1, 30, (n, n))
    dist = (dist + dist.T) / 2
    np.fill_diagonal(dist, 0)
    log_stock = rng.uniform(8, 12, n)
    nuevas = rng.uniform(0, 0.3, n)
    return dist, log_stock, nuevas


def test_shares_have_zero_diagonal_and_rows_summing_to_one():
    dist, log_stock, nuevas = _caracteristicas()
    s = shares_destinos((1.0, 0.1, 2.0), dist, log_stock, nuevas)
    np.testing.assert_allclose(s.sum(axis=1), 1.0)
    assert np.all(np.diag(s) == 0)


def test_fit_recovers_the_parameters_that_generated_the_flows():
    dist, log_stock, nuevas = _caracteristicas(n=12, seed=3)
    verdad = (0.8, 0.15, 1.5)
    flujos = shares_destinos(verdad, dist, log_stock, nuevas) * 1e7
    theta = ajustar_destinos(flujos, dist, log_stock, nuevas)
    np.testing.assert_allclose(theta, verdad, atol=1e-3)


def test_fit_without_housing_term_keeps_gamma_at_zero():
    dist, log_stock, nuevas = _caracteristicas(n=12, seed=3)
    flujos = shares_destinos((0.8, 0.15, 0.0), dist, log_stock, nuevas) * 1e7
    theta = ajustar_destinos(flujos, dist, log_stock, None)
    assert theta[2] == 0.0
    np.testing.assert_allclose(theta[:2], (0.8, 0.15), atol=1e-3)


def test_pivot_moves_shares_toward_comunas_whose_new_supply_grew():
    base = np.array([[0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0]])
    out = pivote_por_permisos(base, np.array([0.0, 0.0, 0.2]), np.array([0.0, 0.0, 0.0]), 1.0)
    np.testing.assert_allclose(out.sum(axis=1), 1.0)
    assert out[0, 2] > out[0, 1]
    assert np.all(np.diag(out) == 0)


def test_pivot_with_unchanged_supply_returns_the_same_shares():
    base = np.array([[0, 0.3, 0.7], [0.5, 0, 0.5], [0.9, 0.1, 0]])
    g = np.array([0.1, 0.2, 0.3])
    np.testing.assert_allclose(pivote_por_permisos(base, g, g, 2.0), base)


def test_radiation_prefers_the_nearer_of_two_equal_destinations():
    pob = np.array([100.0, 100.0, 100.0])
    dist = np.array([[0, 1, 5], [1, 0, 4], [5, 4, 0]], dtype=float)
    s = radiacion(pob, dist)
    np.testing.assert_allclose(s.sum(axis=1), 1.0)
    assert s[0, 1] > s[0, 2]
    assert np.all(np.diag(s) == 0)


def test_radiation_rejects_mismatched_shapes():
    with pytest.raises(ValueError, match="shape"):
        radiacion(np.ones(3), np.ones((2, 2)))
