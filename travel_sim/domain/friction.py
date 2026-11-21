"""Pure friction_score formulas per docs/travel-simulator/data-model.md section 5."""
from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING

from travel_sim.domain.value_objects import FrictionScore, NumericInput, to_decimal

if TYPE_CHECKING:
    from travel_sim.domain.entities import ServiceOption

MAX_SETUP_TIME_MINUTES = 60
WEIGHT_SETUP_TIME = Decimal(30)

MAX_PAPERWORK_LEVEL = 3
WEIGHT_PAPERWORK = Decimal(25)

WEIGHT_PHYSICAL_PRESENCE = Decimal(20)

MAX_LANGUAGE_BARRIER_LEVEL = 2
WEIGHT_LANGUAGE_BARRIER = Decimal(15)

MAX_UNCERTAINTY_RISK_LEVEL = 2
WEIGHT_UNCERTAINTY_RISK = Decimal(10)

MIN_FRICTION_SCORE = Decimal(0)
MAX_FRICTION_SCORE = Decimal(100)


def calculate_friction_breakdown(option: ServiceOption) -> FrictionScore:
    """Compute option friction score and its five weighted components.

    Formula (data-model.md section 5):
      - S_t = min(60, setup_time_minutes) / 60 * 30          (max 30)
      - P_w = (paperwork_level / 3) * 25                     (max 25)
      - M_p = (1 if physical_presence_required else 0) * 20  (max 20)
      - L_b = (language_barrier_level / 2) * 15              (max 15)
      - U_r = (uncertainty_risk_level / 2) * 10              (max 10)
      - option_friction_score = min(100, S_t + P_w + M_p + L_b + U_r)
    """
    capped_minutes = min(MAX_SETUP_TIME_MINUTES, option.setup_time_minutes)
    setup_time = (Decimal(capped_minutes) * WEIGHT_SETUP_TIME) / Decimal(MAX_SETUP_TIME_MINUTES)
    paperwork = (Decimal(option.paperwork_level) * WEIGHT_PAPERWORK) / Decimal(MAX_PAPERWORK_LEVEL)
    physical_presence = (
        WEIGHT_PHYSICAL_PRESENCE if option.physical_presence_required else Decimal(0)
    )
    language_barrier = (
        Decimal(option.language_barrier_level) * WEIGHT_LANGUAGE_BARRIER
    ) / Decimal(MAX_LANGUAGE_BARRIER_LEVEL)
    uncertainty_risk = (
        Decimal(option.uncertainty_risk_level) * WEIGHT_UNCERTAINTY_RISK
    ) / Decimal(MAX_UNCERTAINTY_RISK_LEVEL)

    raw_total = setup_time + paperwork + physical_presence + language_barrier + uncertainty_risk
    bounded_total = max(MIN_FRICTION_SCORE, min(MAX_FRICTION_SCORE, raw_total))
    return FrictionScore(
        value=bounded_total,
        setup_time=setup_time,
        paperwork=paperwork,
        physical_presence=physical_presence,
        language_barrier=language_barrier,
        uncertainty_risk=uncertainty_risk,
    )


def friction_score(option: ServiceOption) -> Decimal:
    """Return the scalar friction score in [0, 100] for a single service option."""
    return calculate_friction_breakdown(option).value


def scenario_friction_score(
    options: Sequence[ServiceOption],
    penalty_handoff: NumericInput = Decimal(0),
) -> Decimal:
    """Aggregate friction across selected scenario options plus handoff penalty.

    Formula (data-model.md section 5.3):
      scenario_friction_score = (1 / |O|) * sum(option_friction_score(o)) + penalty_handoff
    Clamped to [0, 100] to preserve the documented friction scale.
    """
    if not options:
        raise ValueError("options must contain at least one ServiceOption")

    penalty = to_decimal(penalty_handoff, "penalty_handoff")
    if penalty < 0:
        raise ValueError(f"penalty_handoff must be non-negative, got {penalty}")

    total = sum((friction_score(opt) for opt in options), start=Decimal(0))
    mean_score = total / Decimal(len(options))
    return max(MIN_FRICTION_SCORE, min(MAX_FRICTION_SCORE, mean_score + penalty))
