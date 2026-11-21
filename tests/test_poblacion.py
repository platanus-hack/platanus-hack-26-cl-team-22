"""Open population projection: internal moves plus births, deaths and external flows."""

import numpy as np
import pytest

from core.hogares import MigrationModel
from experiments.validar_poblacion import TasasAbiertas, proyectar


def _modelo_quieto(n=2):
    return MigrationModel(np.zeros(n), np.zeros((n, n)))


def _tasas(n=2, **kw):
    base = {k: np.zeros(n) for k in ("natalidad", "mortalidad", "llegan_regiones",
                                      "llegan_extranjero", "salen_regiones")}
    base.update({k: np.asarray(v, dtype=float) for k, v in kw.items()})
    return TasasAbiertas(**base)


def test_zero_external_rates_reduce_to_the_closed_model():
    matriz = np.array([[90.0, 10.0], [5.0, 95.0]])
    modelo = MigrationModel.from_census(matriz)
    pob = np.array([1000.0, 2000.0])
    cerrado, _ = modelo.run(pob, 3)
    np.testing.assert_allclose(proyectar(modelo, pob, _tasas(), 3), cerrado)


def test_births_and_deaths_change_each_comuna_by_its_own_rates():
    out = proyectar(_modelo_quieto(), np.array([1000.0, 1000.0]),
                    _tasas(natalidad=[0.02, 0.0], mortalidad=[0.0, 0.01]), 1)
    np.testing.assert_allclose(out[-1], [1020.0, 990.0])


def test_external_arrivals_add_and_departures_subtract():
    out = proyectar(_modelo_quieto(), np.array([1000.0, 1000.0]),
                    _tasas(llegan_extranjero=[0.03, 0.0], llegan_regiones=[0.01, 0.0],
                           salen_regiones=[0.0, 0.05]), 1)
    np.testing.assert_allclose(out[-1], [1040.0, 950.0])


def test_projection_has_one_row_per_year_and_starts_at_the_initial_population():
    pob = np.array([10.0, 20.0])
    out = proyectar(_modelo_quieto(), pob, _tasas(natalidad=[0.1, 0.1]), 7)
    assert out.shape == (8, 2)
    np.testing.assert_allclose(out[0], pob)


def test_population_never_goes_negative():
    out = proyectar(_modelo_quieto(), np.array([10.0, 10.0]),
                    _tasas(salen_regiones=[2.0, 0.0]), 1)
    assert np.all(out >= 0)


def test_rejects_rates_of_the_wrong_shape():
    with pytest.raises(ValueError, match="shape"):
        proyectar(_modelo_quieto(), np.array([1.0, 1.0]), _tasas(n=3), 1)
