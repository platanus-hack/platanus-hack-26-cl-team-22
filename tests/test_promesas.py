import numpy as np
import pytest

from experiments.promesas import (
    CUT,
    HIGH_CREDIBILITY,
    LOW_CREDIBILITY,
    VARIANTS,
    build_package,
    spreadsheet_value,
)
from experiments.simular import load_setup


@pytest.fixture(scope="module")
def setup():
    return load_setup()


def weights(setup):
    return setup.state.population / setup.state.population.sum()


def test_packages_have_the_promised_structure(setup):
    many_one = build_package(setup, "muchas-promesas-un-ejecutor", 10)
    many_munis = build_package(setup, "muchas-promesas-18-municipios", 10)
    few = build_package(setup, "pocas-promesas", 10)
    assert len(many_one) == len(many_munis) == 18
    assert len(few) == 1
    assert len({iv.measure.executor for iv in many_one}) == 1
    assert len({iv.measure.executor for iv in many_munis}) == 18
    assert np.array_equal(np.logical_or.reduce([iv.communes for iv in many_one]), setup.in_b)
    assert np.array_equal(few[0].communes, setup.in_b)


def test_a_spreadsheet_sees_both_packages_as_equal(setup):
    credibility = {"muchas-promesas-un-ejecutor": LOW_CREDIBILITY,
                   "muchas-promesas-18-municipios": LOW_CREDIBILITY,
                   "pocas-promesas": HIGH_CREDIBILITY}
    values = [spreadsheet_value(setup, build_package(setup, v, 10), weights(setup),
                                credibility[v]) for v in VARIANTS]
    assert values == pytest.approx([values[0]] * 3, abs=1e-9)
    assert CUT * HIGH_CREDIBILITY == pytest.approx(LOW_CREDIBILITY)


def test_full_delivery_of_the_small_promise_is_its_best_case(setup):
    few = build_package(setup, "pocas-promesas", 10)
    full_value = spreadsheet_value(setup, few, weights(setup), 1.0)
    assert full_value < setup.state.pm25 @ weights(setup)
    assert few[0].factor_at_full == pytest.approx(1 - CUT)
