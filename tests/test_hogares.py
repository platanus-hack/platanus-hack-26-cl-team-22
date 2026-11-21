import numpy as np
import pytest

from core.hogares import MigrationModel, net_migration

# 3 communes; rows = origin 5 years ago, columns = destination now.
CENSUS = np.array([
    [800.0, 150.0, 50.0],
    [20.0, 950.0, 30.0],
    [0.0, 0.0, 500.0],
])


def model():
    return MigrationModel.from_census(CENSUS)


def test_out_rate_is_the_annualised_share_that_leaves():
    m = model()
    five_year = np.array([200 / 1000, 50 / 1000, 0.0])
    assert np.allclose(1 - (1 - m.out_rate) ** 5, five_year)
    assert m.out_rate[2] == 0.0


def test_shares_follow_where_leavers_went():
    m = model()
    assert np.allclose(m.shares[0], [0.0, 0.75, 0.25])
    assert np.allclose(m.shares[1], [0.4, 0.0, 0.6])
    assert np.allclose(m.shares[2], 0.0)


def test_total_population_is_conserved_when_people_move():
    m = model()
    pops, flows = m.run(np.array([1000.0, 1000.0, 500.0]), n_years=20)
    assert np.allclose(pops.sum(axis=1), 2500.0)
    assert flows.shape == (20, 3, 3)


def test_zero_out_rate_changes_nothing():
    m = MigrationModel(np.zeros(3), model().shares)
    pops, _ = m.run(np.array([1000.0, 1000.0, 500.0]), n_years=5)
    assert np.allclose(pops, pops[0])


def test_five_annual_steps_reproduce_the_census_out_flows_from_the_origin():
    m = model()
    _, flows = m.run(CENSUS.sum(axis=1), n_years=1)
    first_year_out = flows[0].sum(axis=1)
    assert np.allclose(first_year_out, CENSUS.sum(axis=1) * m.out_rate)


def test_capacity_is_respected_and_blocked_movers_stay():
    m = model()
    population = np.array([1000.0, 1000.0, 500.0])
    capacity = np.array([2000.0, 1010.0, 2000.0])
    new, _ = m.step(population, capacity)
    assert new[1] <= 1010.0 + 1e-9
    assert np.isclose(new.sum(), population.sum())
    unconstrained, _ = m.step(population)
    assert new[0] > unconstrained[0]  # people who could not move to commune 1 stayed


def test_net_migration_is_arrivals_minus_departures():
    assert np.allclose(net_migration(CENSUS), [-180.0, 100.0, 80.0])


@pytest.mark.parametrize(
    "call",
    [
        lambda: MigrationModel.from_census(np.ones((2, 3))),
        lambda: MigrationModel.from_census(-np.ones((2, 2))),
        lambda: MigrationModel(np.array([1.5, 0.0]), np.zeros((2, 2))),
        lambda: MigrationModel(np.zeros(2), np.array([[0.5, 0.5], [1.0, 0.0]])),
        lambda: MigrationModel(np.zeros(2), np.array([[0.0, 0.7], [1.0, 0.0]])),
        lambda: model().step(np.array([1.0, 2.0])),
    ],
)
def test_invalid_inputs_are_rejected(call):
    with pytest.raises(ValueError):
        call()
