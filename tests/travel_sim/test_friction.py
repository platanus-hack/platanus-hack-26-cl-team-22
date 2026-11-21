"""Unit tests for friction_score weights, bounds 0..100, and scenario aggregation."""
from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from travel_sim.domain import (
    MAX_FRICTION_SCORE,
    MIN_FRICTION_SCORE,
    WEIGHT_LANGUAGE_BARRIER,
    WEIGHT_PAPERWORK,
    WEIGHT_PHYSICAL_PRESENCE,
    WEIGHT_SETUP_TIME,
    WEIGHT_UNCERTAINTY_RISK,
    ServiceOption,
    calculate_friction_breakdown,
    friction_score,
    scenario_friction_score,
)


def test_weights_sum_to_100() -> None:
    total_weight = (
        WEIGHT_SETUP_TIME
        + WEIGHT_PAPERWORK
        + WEIGHT_PHYSICAL_PRESENCE
        + WEIGHT_LANGUAGE_BARRIER
        + WEIGHT_UNCERTAINTY_RISK
    )
    assert total_weight == Decimal(100)


def test_zero_friction_lower_bound(make_option: Callable[..., ServiceOption]) -> None:
    opt = make_option(
        setup_time_minutes=0,
        paperwork_level=0,
        physical_presence_required=False,
        language_barrier_level=0,
        uncertainty_risk_level=0,
    )
    breakdown = calculate_friction_breakdown(opt)
    assert breakdown.value == MIN_FRICTION_SCORE == Decimal(0)
    assert breakdown.setup_time == Decimal(0)
    assert breakdown.paperwork == Decimal(0)
    assert breakdown.physical_presence == Decimal(0)
    assert breakdown.language_barrier == Decimal(0)
    assert breakdown.uncertainty_risk == Decimal(0)
    assert opt.friction_score() == Decimal(0)


def test_max_friction_upper_bound_and_setup_time_cap(
    make_option: Callable[..., ServiceOption],
) -> None:
    opt = make_option(
        setup_time_minutes=180,  # exceeds 60-minute cap
        paperwork_level=3,
        physical_presence_required=True,
        language_barrier_level=2,
        uncertainty_risk_level=2,
    )
    breakdown = calculate_friction_breakdown(opt)
    assert breakdown.setup_time == Decimal(30)
    assert breakdown.paperwork == Decimal(25)
    assert breakdown.physical_presence == Decimal(20)
    assert breakdown.language_barrier == Decimal(15)
    assert breakdown.uncertainty_risk == Decimal(10)
    assert breakdown.value == MAX_FRICTION_SCORE == Decimal(100)


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"setup_time_minutes": 30}, Decimal(15)),
        ({"setup_time_minutes": 60}, Decimal(30)),
        ({"setup_time_minutes": 120}, Decimal(30)),
        ({"paperwork_level": 3}, Decimal(25)),
        ({"physical_presence_required": True}, Decimal(20)),
        ({"language_barrier_level": 1}, Decimal("7.5")),
        ({"language_barrier_level": 2}, Decimal(15)),
        ({"uncertainty_risk_level": 1}, Decimal(5)),
        ({"uncertainty_risk_level": 2}, Decimal(10)),
    ],
)
def test_individual_factor_weights(
    make_option: Callable[..., ServiceOption],
    kwargs: dict[str, object],
    expected: Decimal,
) -> None:
    opt = make_option(**kwargs)
    assert friction_score(opt) == expected


def test_paperwork_fractional_weight_precision(
    make_option: Callable[..., ServiceOption],
) -> None:
    opt_1 = make_option(paperwork_level=1)
    opt_2 = make_option(paperwork_level=2)
    assert friction_score(opt_1) == Decimal(25) / Decimal(3)
    assert friction_score(opt_2) == Decimal(50) / Decimal(3)


def test_combined_midrange_score_within_bounds(
    make_option: Callable[..., ServiceOption],
) -> None:
    opt = make_option(
        setup_time_minutes=20,  # 10
        paperwork_level=3,  # 25
        physical_presence_required=True,  # 20
        language_barrier_level=1,  # 7.5
        uncertainty_risk_level=1,  # 5
    )
    score = friction_score(opt)
    assert score == Decimal("67.5")
    assert Decimal(0) <= score <= Decimal(100)


def test_scenario_friction_score_mean_and_handoff_penalty(
    make_option: Callable[..., ServiceOption],
) -> None:
    low = make_option(id="low", setup_time_minutes=20)  # 10
    high = make_option(
        id="high",
        setup_time_minutes=60,  # 30
        physical_presence_required=True,  # 20
    )  # 50
    assert scenario_friction_score([low, high]) == Decimal(30)
    assert scenario_friction_score([low, high], penalty_handoff=Decimal("5.5")) == Decimal("35.5")


def test_scenario_friction_score_clamps_to_100(
    make_option: Callable[..., ServiceOption],
) -> None:
    maxed = make_option(
        setup_time_minutes=60,
        paperwork_level=3,
        physical_presence_required=True,
        language_barrier_level=2,
        uncertainty_risk_level=2,
    )
    assert scenario_friction_score([maxed], penalty_handoff=Decimal(15)) == Decimal(100)


@pytest.mark.parametrize(
    "bad_kwargs",
    [
        {"setup_time_minutes": -1},
        {"paperwork_level": -1},
        {"paperwork_level": 4},
        {"language_barrier_level": -1},
        {"language_barrier_level": 3},
        {"uncertainty_risk_level": -1},
        {"uncertainty_risk_level": 3},
    ],
)
def test_invalid_friction_inputs_rejected(
    make_option: Callable[..., ServiceOption],
    bad_kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        make_option(**bad_kwargs)


def test_scenario_friction_rejects_empty_options_or_negative_penalty(
    make_option: Callable[..., ServiceOption],
) -> None:
    with pytest.raises(ValueError):
        scenario_friction_score([])
    with pytest.raises(ValueError):
        scenario_friction_score([make_option()], penalty_handoff=Decimal(-1))
