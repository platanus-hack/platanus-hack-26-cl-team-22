"""Network rule of the moves simulation: arrivals from abroad follow the foreign-born stock."""

import numpy as np

from experiments.validar_redes import ajustar_phi, pesos_redes


def test_weights_are_shares_of_stock_plus_one_to_the_power_phi():
    w = pesos_redes(np.array([0.0, 3.0]), 1.0)
    np.testing.assert_allclose(w, [0.2, 0.8])


def test_phi_zero_spreads_arrivals_evenly():
    np.testing.assert_allclose(pesos_redes(np.array([0.0, 99.0, 9.0]), 0.0), [1 / 3] * 3)


def test_fit_recovers_the_phi_that_generated_the_arrivals():
    stock = np.array([10.0, 100.0, 1000.0, 5000.0, 20.0])
    llegadas = pesos_redes(stock, 0.8) * 1e6
    assert abs(ajustar_phi(llegadas, stock) - 0.8) < 1e-4
