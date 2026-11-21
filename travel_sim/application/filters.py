"""Pure hard-filter and soft-filter logic per docs/travel-simulator/engine-spec.md."""
from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Protocol

from travel_sim.domain import (
    PaymentMethodPreference,
    ServiceCategory,
    ServiceOption,
    SimType,
    TravelerProfile,
    friction_score,
    packages_needed,
    packages_needed_for_data,
)
from travel_sim.domain.value_objects import NumericInput, to_decimal

DEFAULT_BALANCED_EFFICIENCY_THRESHOLD_USD = Decimal("0.75")
DEFAULT_BALANCED_MAX_FRICTION = Decimal(50)
_LEXICOGRAPHIC_WEIGHT = Decimal(1000)


class RejectionReason(str, Enum):
    """Deterministic hard-filter rejection causes."""

    CITY_MISMATCH = "CITY_MISMATCH"
    UNSUPPORTED_PHYSICAL_SIM = "UNSUPPORTED_PHYSICAL_SIM"
    UNSUPPORTED_ESIM = "UNSUPPORTED_ESIM"
    REQUIRES_LOCAL_ID = "REQUIRES_LOCAL_ID"
    PAYMENT_METHOD_INCOMPATIBLE = "PAYMENT_METHOD_INCOMPATIBLE"
    INSUFFICIENT_DATA_QUOTA = "INSUFFICIENT_DATA_QUOTA"
    INCOMPATIBLE_WITH_SELECTED = "INCOMPATIBLE_WITH_SELECTED"


@dataclass(frozen=True, slots=True)
class RejectedOption:
    """An option excluded by hard filters together with all violated rules."""

    option: ServiceOption
    reasons: tuple[RejectionReason, ...]


@dataclass(frozen=True, slots=True)
class HardFilterResult:
    """Partition of candidate options into eligible and rejected sets."""

    eligible: tuple[ServiceOption, ...]
    rejected: tuple[RejectedOption, ...]


@dataclass(frozen=True, slots=True)
class OptionCriteria:
    """Soft-filter evaluation criteria (C, F, T) per engine-spec.md section 2.2."""

    option: ServiceOption
    total_cost_usd: Decimal
    total_cost_local: Decimal
    daily_cost_usd: Decimal
    friction_score: Decimal
    extra_time_minutes: int


@dataclass(frozen=True, slots=True)
class ScoredOption:
    """An option evaluated and scored by a soft-filter scorer hook."""

    criteria: OptionCriteria
    score: Decimal


class SoftFilterScorer(Protocol):
    """Hook that assigns a numeric objective score (lower is better)."""

    def __call__(self, criteria: OptionCriteria, traveler: TravelerProfile) -> Decimal: ...


class SoftFilterPredicate(Protocol):
    """Hook that keeps or drops an option based on soft criteria."""

    def __call__(self, criteria: OptionCriteria, traveler: TravelerProfile) -> bool: ...


def are_options_compatible(
    option_a: ServiceOption,
    option_b: ServiceOption,
    *,
    incompatible_pairs: Collection[tuple[str, str]] = (),
) -> bool:
    """Return False if two options declare mutual or pair-level incompatibility."""
    if option_b.id in option_a.incompatible_option_ids:
        return False
    if option_a.id in option_b.incompatible_option_ids:
        return False
    for first_id, second_id in incompatible_pairs:
        if (option_a.id == first_id and option_b.id == second_id) or (
            option_a.id == second_id and option_b.id == first_id
        ):
            return False
    return True


def evaluate_hard_filters(
    option: ServiceOption,
    traveler: TravelerProfile,
    *,
    selected_options: Sequence[ServiceOption] = (),
    incompatible_pairs: Collection[tuple[str, str]] = (),
) -> tuple[RejectionReason, ...]:
    """Evaluate all hard filters and return every violated reason in stable order."""
    reasons: list[RejectionReason] = []

    if option.city_id != traveler.destination_city_id:
        reasons.append(RejectionReason.CITY_MISMATCH)

    if option.category == ServiceCategory.CONNECTIVITY:
        if (
            option.sim_type == SimType.PHYSICAL_SIM
            and not traveler.device_profile.supports_physical_sim
        ):
            reasons.append(RejectionReason.UNSUPPORTED_PHYSICAL_SIM)
        elif option.sim_type == SimType.ESIM and not traveler.device_profile.supports_esim:
            reasons.append(RejectionReason.UNSUPPORTED_ESIM)

    if option.requires_local_id and not traveler.has_local_id:
        reasons.append(RejectionReason.REQUIRES_LOCAL_ID)

    if (
        traveler.payment_method_preference == PaymentMethodPreference.CASH
        and option.requires_international_card
    ):
        reasons.append(RejectionReason.PAYMENT_METHOD_INCOMPATIBLE)

    if (
        option.category == ServiceCategory.CONNECTIVITY
        and option.data_quota_gb is not None
        and traveler.target_data_gb > 0
    ):
        base_pkgs = packages_needed(option, traveler.trip_duration_days)
        base_quota = option.data_quota_gb * Decimal(base_pkgs)
        if base_quota < traveler.target_data_gb and (
            not option.allows_top_up or option.data_quota_gb == 0
        ):
            reasons.append(RejectionReason.INSUFFICIENT_DATA_QUOTA)

    for selected in selected_options:
        if not are_options_compatible(option, selected, incompatible_pairs=incompatible_pairs):
            reasons.append(RejectionReason.INCOMPATIBLE_WITH_SELECTED)
            break

    return tuple(reasons)


def is_option_eligible(
    option: ServiceOption,
    traveler: TravelerProfile,
    *,
    selected_options: Sequence[ServiceOption] = (),
    incompatible_pairs: Collection[tuple[str, str]] = (),
) -> bool:
    """Return True iff option satisfies all hard filters for traveler."""
    return not evaluate_hard_filters(
        option,
        traveler,
        selected_options=selected_options,
        incompatible_pairs=incompatible_pairs,
    )


def apply_hard_filters(
    options: Sequence[ServiceOption],
    traveler: TravelerProfile,
    *,
    selected_options: Sequence[ServiceOption] = (),
    incompatible_pairs: Collection[tuple[str, str]] = (),
) -> HardFilterResult:
    """Deterministically partition options into eligible and rejected collections."""
    eligible: list[ServiceOption] = []
    rejected: list[RejectedOption] = []

    for option in options:
        reasons = evaluate_hard_filters(
            option,
            traveler,
            selected_options=selected_options,
            incompatible_pairs=incompatible_pairs,
        )
        if reasons:
            rejected.append(RejectedOption(option=option, reasons=reasons))
        else:
            eligible.append(option)

    return HardFilterResult(eligible=tuple(eligible), rejected=tuple(rejected))


def _billable_packages_for_traveler(option: ServiceOption, traveler: TravelerProfile) -> int:
    if (
        option.category == ServiceCategory.CONNECTIVITY
        and option.data_quota_gb is not None
        and option.data_quota_gb > 0
        and option.allows_top_up
        and traveler.target_data_gb > 0
    ):
        return packages_needed_for_data(
            option, traveler.trip_duration_days, traveler.target_data_gb
        )
    return packages_needed(option, traveler.trip_duration_days)


def compute_option_criteria(
    options: Sequence[ServiceOption],
    traveler: TravelerProfile,
) -> tuple[OptionCriteria, ...]:
    """Compute soft-filter criteria (C, F, T) for each candidate option.

    Extra time (T) is measured in minutes relative to the lowest-friction option
    in the provided candidate set (tie-broken by total USD cost, then option.id).
    """
    if not options:
        return ()

    raw_rows: list[tuple[ServiceOption, Decimal, Decimal, Decimal, Decimal]] = []
    days = Decimal(traveler.trip_duration_days)
    for option in options:
        pkgs = Decimal(_billable_packages_for_traveler(option, traveler))
        total_usd = pkgs * option.cost_usd_reference
        total_local = pkgs * option.cost_local_currency
        daily_usd = total_usd / days
        f_score = friction_score(option)
        raw_rows.append((option, total_usd, total_local, daily_usd, f_score))

    baseline_option = min(raw_rows, key=lambda row: (row[4], row[1], row[0].id))[0]
    baseline_setup = baseline_option.setup_time_minutes

    return tuple(
        OptionCriteria(
            option=opt,
            total_cost_usd=total_usd,
            total_cost_local=total_local,
            daily_cost_usd=daily_usd,
            friction_score=f_score,
            extra_time_minutes=max(0, opt.setup_time_minutes - baseline_setup),
        )
        for opt, total_usd, total_local, daily_usd, f_score in raw_rows
    )


def zero_friction_scorer(criteria: OptionCriteria, traveler: TravelerProfile) -> Decimal:
    """Zero-friction objective per engine-spec.md section 3.1: F * 1000 + C."""
    del traveler
    return criteria.friction_score * _LEXICOGRAPHIC_WEIGHT + criteria.total_cost_usd


def local_optimized_scorer(criteria: OptionCriteria, traveler: TravelerProfile) -> Decimal:
    """Local-optimized objective per engine-spec.md section 3.2: C * 1000 + F."""
    del traveler
    return criteria.total_cost_usd * _LEXICOGRAPHIC_WEIGHT + criteria.friction_score


def make_weighted_scorer(
    *,
    cost_weight: NumericInput,
    friction_weight: NumericInput,
    extra_time_weight: NumericInput = Decimal(0),
) -> SoftFilterScorer:
    """Build a linear soft-filter scorer over (C, F, T)."""
    w_cost = to_decimal(cost_weight, "cost_weight")
    w_friction = to_decimal(friction_weight, "friction_weight")
    w_time = to_decimal(extra_time_weight, "extra_time_weight")
    if w_cost < 0 or w_friction < 0 or w_time < 0:
        raise ValueError("scorer weights must be non-negative")

    def _score(criteria: OptionCriteria, traveler: TravelerProfile) -> Decimal:
        del traveler
        return (
            w_cost * criteria.total_cost_usd
            + w_friction * criteria.friction_score
            + w_time * Decimal(criteria.extra_time_minutes)
        )

    return _score


def make_max_friction_predicate(max_friction: NumericInput) -> SoftFilterPredicate:
    """Build a soft-filter predicate rejecting options above max_friction."""
    limit = to_decimal(max_friction, "max_friction")
    if not (Decimal(0) <= limit <= Decimal(100)):
        raise ValueError(f"max_friction must be in [0, 100], got {limit}")

    def _predicate(criteria: OptionCriteria, traveler: TravelerProfile) -> bool:
        del traveler
        return criteria.friction_score <= limit

    return _predicate


def make_balanced_substitution_predicate(
    baseline: OptionCriteria,
    *,
    min_usd_per_friction_point: NumericInput = DEFAULT_BALANCED_EFFICIENCY_THRESHOLD_USD,
    max_friction: NumericInput = DEFAULT_BALANCED_MAX_FRICTION,
) -> SoftFilterPredicate:
    """Build the balanced marginal-efficiency hook per engine-spec.md section 3.3.

    Accepts a candidate option when its friction_score <= max_friction and
    replacing baseline saves money at >= min_usd_per_friction_point USD per added
    friction point (or strictly dominates baseline with lower cost and <= friction).
    """
    theta = to_decimal(min_usd_per_friction_point, "min_usd_per_friction_point")
    limit = to_decimal(max_friction, "max_friction")
    if theta < 0:
        raise ValueError(f"min_usd_per_friction_point must be >= 0, got {theta}")
    if not (Decimal(0) <= limit <= Decimal(100)):
        raise ValueError(f"max_friction must be in [0, 100], got {limit}")

    def _predicate(criteria: OptionCriteria, traveler: TravelerProfile) -> bool:
        del traveler
        if criteria.friction_score > limit:
            return False
        savings = baseline.total_cost_usd - criteria.total_cost_usd
        if savings <= 0:
            return False
        delta_friction = criteria.friction_score - baseline.friction_score
        if delta_friction <= 0:
            return True
        return (savings / delta_friction) >= theta

    return _predicate


def apply_soft_filters(
    options: Sequence[ServiceOption],
    traveler: TravelerProfile,
    *,
    scorer: SoftFilterScorer,
    predicates: Sequence[SoftFilterPredicate] = (),
) -> tuple[ScoredOption, ...]:
    """Evaluate soft criteria, filter via predicates, score, and rank deterministically."""
    criteria_list = compute_option_criteria(options, traveler)
    scored: list[ScoredOption] = []
    for criteria in criteria_list:
        if all(predicate(criteria, traveler) for predicate in predicates):
            score = to_decimal(scorer(criteria, traveler), "score")
            scored.append(ScoredOption(criteria=criteria, score=score))

    scored.sort(key=lambda item: (item.score, item.criteria.option.id))
    return tuple(scored)
