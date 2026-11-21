"""AI-assistant audit pipeline comparing recommendations against the deterministic engine."""
from __future__ import annotations

import json
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from travel_sim.application.filters import (
    RejectionReason,
    apply_hard_filters,
    compute_option_criteria,
    evaluate_hard_filters,
)
from travel_sim.application.ports import AssistantPort, OptionRepository
from travel_sim.application.scenarios import TripScenario
from travel_sim.application.simulate import simulate
from travel_sim.domain import (
    MAX_FRICTION_SCORE,
    MIN_FRICTION_SCORE,
    City,
    ServiceCategory,
    ServiceOption,
    TravelerProfile,
    scenario_friction_score,
)
from travel_sim.domain.value_objects import NumericInput, to_decimal

UNMAPPED_RECOMMENDATION_FLAG = "UNMAPPED_RECOMMENDATION"
_ZERO = Decimal(0)
_HUNDRED = Decimal(100)
_NORMAL_95_Z = 1.959963984540054


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    """Sample mean and two-sided 95% confidence interval computed with stdlib math."""

    mean: Decimal
    lower: Decimal
    upper: Decimal
    margin_of_error: Decimal
    std_dev: Decimal
    sample_size: int
    confidence_level: Decimal = Decimal("0.95")

    def to_dict(self) -> dict[str, Any]:
        """Serialize confidence interval to JSON-compatible primitives."""
        return {
            "mean": float(self.mean),
            "lower": float(self.lower),
            "upper": float(self.upper),
            "margin_of_error": float(self.margin_of_error),
            "std_dev": float(self.std_dev),
            "sample_size": self.sample_size,
            "confidence_level": float(self.confidence_level),
        }


@dataclass(frozen=True, slots=True)
class ParsedRecommendation:
    """Validated mapping from service categories to catalog options (or None)."""

    raw_reply: str
    is_valid: bool
    selections: Mapping[ServiceCategory, ServiceOption | None]
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecommendationScore:
    """Engine-computed cost, friction, feasibility, and scenario deltas for one reply."""

    selections: Mapping[ServiceCategory, ServiceOption | None]
    selected_options: tuple[ServiceOption, ...]
    null_categories: tuple[ServiceCategory, ...]
    is_feasible: bool
    infeasibility_reasons: Mapping[ServiceCategory, tuple[RejectionReason, ...]]
    total_cost_usd: Decimal
    total_cost_local: Decimal
    total_cost_clp: Decimal
    friction_score: Decimal
    total_friction_score: Decimal
    overpayment_vs_local_usd: Decimal
    overpayment_vs_local_clp: Decimal
    overpayment_vs_local_pct: Decimal
    extra_friction_vs_local: Decimal
    overpayment_vs_zero_friction_usd: Decimal
    overpayment_vs_zero_friction_clp: Decimal
    overpayment_vs_zero_friction_pct: Decimal
    extra_friction_vs_zero_friction: Decimal
    unmapped_categories: tuple[ServiceCategory, ...] = ()
    flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize recommendation score to JSON-compatible primitives."""
        return {
            "selections": {
                cat.value: (opt.id if opt is not None else None)
                for cat, opt in self.selections.items()
            },
            "selected_option_ids": [opt.id for opt in self.selected_options],
            "null_categories": [cat.value for cat in self.null_categories],
            "unmapped_categories": [cat.value for cat in self.unmapped_categories],
            "flags": list(self.flags),
            "is_feasible": self.is_feasible,
            "infeasibility_reasons": {
                cat.value: [reason.value for reason in reasons]
                for cat, reasons in self.infeasibility_reasons.items()
            },
            "total_cost_usd": float(self.total_cost_usd),
            "total_cost_local": float(self.total_cost_local),
            "total_cost_clp": float(self.total_cost_clp),
            "friction_score": float(self.friction_score),
            "total_friction_score": float(self.total_friction_score),
            "overpayment_vs_local_usd": float(self.overpayment_vs_local_usd),
            "overpayment_vs_local_clp": float(self.overpayment_vs_local_clp),
            "overpayment_vs_local_pct": float(self.overpayment_vs_local_pct),
            "extra_friction_vs_local": float(self.extra_friction_vs_local),
            "overpayment_vs_zero_friction_usd": float(self.overpayment_vs_zero_friction_usd),
            "overpayment_vs_zero_friction_clp": float(self.overpayment_vs_zero_friction_clp),
            "overpayment_vs_zero_friction_pct": float(self.overpayment_vs_zero_friction_pct),
            "extra_friction_vs_zero_friction": float(self.extra_friction_vs_zero_friction),
        }


@dataclass(frozen=True, slots=True)
class ReplicationAuditResult:
    """Single replication result for an AI assistant."""

    replication_index: int
    salt: str
    raw_reply: str
    is_valid: bool
    is_feasible: bool
    validation_errors: tuple[str, ...]
    score: RecommendationScore | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize replication result to JSON-compatible primitives."""
        return {
            "replication_index": self.replication_index,
            "salt": self.salt,
            "raw_reply": self.raw_reply,
            "is_valid": self.is_valid,
            "is_feasible": self.is_feasible,
            "validation_errors": list(self.validation_errors),
            "score": self.score.to_dict() if self.score is not None else None,
        }


@dataclass(frozen=True, slots=True)
class AssistantAuditSummary:
    """Aggregated audit metrics and 95% confidence intervals for one assistant."""

    assistant_name: str
    replications: tuple[ReplicationAuditResult, ...]
    total_replications: int
    valid_count: int
    invalid_count: int
    feasible_count: int
    infeasible_count: int
    validity_rate: Decimal
    infeasibility_rate: Decimal
    total_cost_usd: ConfidenceInterval | None
    total_cost_clp: ConfidenceInterval | None
    friction_score: ConfidenceInterval | None
    overpayment_vs_local_usd: ConfidenceInterval | None
    overpayment_vs_local_clp: ConfidenceInterval | None
    overpayment_vs_local_pct: ConfidenceInterval | None
    extra_friction_vs_local: ConfidenceInterval | None
    overpayment_vs_zero_friction_usd: ConfidenceInterval | None
    overpayment_vs_zero_friction_clp: ConfidenceInterval | None
    overpayment_vs_zero_friction_pct: ConfidenceInterval | None
    extra_friction_vs_zero_friction: ConfidenceInterval | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize assistant audit summary to JSON-compatible primitives."""
        return {
            "assistant_name": self.assistant_name,
            "total_replications": self.total_replications,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "feasible_count": self.feasible_count,
            "infeasible_count": self.infeasible_count,
            "validity_rate": float(self.validity_rate),
            "infeasibility_rate": float(self.infeasibility_rate),
            "total_cost_usd": (
                self.total_cost_usd.to_dict() if self.total_cost_usd is not None else None
            ),
            "total_cost_clp": (
                self.total_cost_clp.to_dict() if self.total_cost_clp is not None else None
            ),
            "friction_score": (
                self.friction_score.to_dict() if self.friction_score is not None else None
            ),
            "overpayment_vs_local_usd": (
                self.overpayment_vs_local_usd.to_dict()
                if self.overpayment_vs_local_usd is not None
                else None
            ),
            "overpayment_vs_local_clp": (
                self.overpayment_vs_local_clp.to_dict()
                if self.overpayment_vs_local_clp is not None
                else None
            ),
            "overpayment_vs_local_pct": (
                self.overpayment_vs_local_pct.to_dict()
                if self.overpayment_vs_local_pct is not None
                else None
            ),
            "extra_friction_vs_local": (
                self.extra_friction_vs_local.to_dict()
                if self.extra_friction_vs_local is not None
                else None
            ),
            "overpayment_vs_zero_friction_usd": (
                self.overpayment_vs_zero_friction_usd.to_dict()
                if self.overpayment_vs_zero_friction_usd is not None
                else None
            ),
            "overpayment_vs_zero_friction_clp": (
                self.overpayment_vs_zero_friction_clp.to_dict()
                if self.overpayment_vs_zero_friction_clp is not None
                else None
            ),
            "overpayment_vs_zero_friction_pct": (
                self.overpayment_vs_zero_friction_pct.to_dict()
                if self.overpayment_vs_zero_friction_pct is not None
                else None
            ),
            "extra_friction_vs_zero_friction": (
                self.extra_friction_vs_zero_friction.to_dict()
                if self.extra_friction_vs_zero_friction is not None
                else None
            ),
            "replications": [rep.to_dict() for rep in self.replications],
        }


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Complete multi-assistant audit report against deterministic baselines."""

    city_id: str
    city_name: str | None
    local_currency: str | None
    traveler: TravelerProfile
    categories: tuple[ServiceCategory, ...]
    prompt: str
    zero_friction_baseline: TripScenario
    local_optimized_baseline: TripScenario
    assistants: Mapping[str, AssistantAuditSummary]

    def to_dict(self) -> dict[str, Any]:
        """Serialize complete audit report to JSON-compatible primitives."""
        return {
            "city_id": self.city_id,
            "city_name": self.city_name,
            "local_currency": self.local_currency,
            "traveler": {
                "id": self.traveler.id,
                "destination_city_id": self.traveler.destination_city_id,
                "trip_duration_days": self.traveler.trip_duration_days,
                "has_local_id": self.traveler.has_local_id,
                "target_data_gb": float(self.traveler.target_data_gb),
                "friction_tolerance": (
                    self.traveler.friction_tolerance.value
                    if hasattr(self.traveler.friction_tolerance, "value")
                    else float(self.traveler.friction_tolerance)
                ),
                "device_profile": {
                    "supports_physical_sim": self.traveler.device_profile.supports_physical_sim,
                    "supports_esim": self.traveler.device_profile.supports_esim,
                },
                "include_day_trips": self.traveler.include_day_trips,
                "dining_preference": self.traveler.dining_preference.value,
                "payment_method_preference": self.traveler.payment_method_preference.value,
            },
            "categories": [cat.value for cat in self.categories],
            "prompt": self.prompt,
            "baselines": {
                "zero_friction": _baseline_to_dict(self.zero_friction_baseline),
                "local_optimized": _baseline_to_dict(self.local_optimized_baseline),
            },
            "assistants": {
                name: summary.to_dict() for name, summary in self.assistants.items()
            },
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        """Render the audit report as a deterministic JSON string."""
        return format_audit_report_json(self, indent=indent)

    def to_text(self) -> str:
        """Render the audit report as a human-readable text summary."""
        return format_audit_report_text(self)


def _baseline_to_dict(scenario: TripScenario) -> dict[str, Any]:
    return {
        "scenario_type": scenario.scenario_type.value,
        "total_cost_usd": float(scenario.total_cost_usd),
        "total_cost_local": float(scenario.total_cost_local),
        "total_cost_clp": float(scenario.total_cost_clp),
        "friction_score": float(scenario.friction_score),
        "choices": {
            cat.value: (choice.option.id if choice is not None else None)
            for cat, choice in scenario.choices_by_category.items()
        },
    }


def _betacf(a: float, b: float, x: float) -> float:
    """Evaluate continued fraction for incomplete beta function via Lentz's method."""
    max_iter = 200
    eps = 3.0e-12
    fpmin = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b) using only stdlib math."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _student_t_critical_95(df: int) -> float:
    """Two-tailed 95% Student's t critical value t_{0.975, df} using stdlib math."""
    if df < 1:
        raise ValueError(f"degrees of freedom must be >= 1, got {df}")
    if df == 1:
        return math.tan(0.475 * math.pi)
    if df > 10000:
        return _NORMAL_95_Z

    low = 1.95
    high = 13.0
    half_nu = 0.5 * df
    for _ in range(70):
        mid = 0.5 * (low + high)
        x = df / (df + mid * mid)
        two_tail_p = _betainc(half_nu, 0.5, x)
        if two_tail_p > 0.05:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def compute_confidence_interval_95(
    values: Sequence[NumericInput],
) -> ConfidenceInterval | None:
    """Compute sample mean and 95% two-sided t-interval using only the standard library."""
    if not values:
        return None

    decimals = [to_decimal(v, "value") for v in values]
    n = len(decimals)
    mean = sum(decimals, start=_ZERO) / Decimal(n)

    if n == 1:
        return ConfidenceInterval(
            mean=mean,
            lower=mean,
            upper=mean,
            margin_of_error=_ZERO,
            std_dev=_ZERO,
            sample_size=1,
        )

    sq_diffs = sum(((x - mean) * (x - mean) for x in decimals), start=_ZERO)
    variance = sq_diffs / Decimal(n - 1)
    std_dev = variance.sqrt() if variance > _ZERO else _ZERO
    if std_dev == _ZERO:
        return ConfidenceInterval(
            mean=mean,
            lower=mean,
            upper=mean,
            margin_of_error=_ZERO,
            std_dev=_ZERO,
            sample_size=n,
        )

    t_crit = Decimal(str(_student_t_critical_95(n - 1)))
    std_err = std_dev / Decimal(n).sqrt()
    margin = t_crit * std_err
    return ConfidenceInterval(
        mean=mean,
        lower=mean - margin,
        upper=mean + margin,
        margin_of_error=margin,
        std_dev=std_dev,
        sample_size=n,
    )


def _resolve_audit_categories(
    options: Sequence[ServiceOption],
    traveler: TravelerProfile,
    explicit_categories: Sequence[ServiceCategory] | None,
) -> tuple[ServiceCategory, ...]:
    if explicit_categories is not None:
        ordered: list[ServiceCategory] = []
        for cat in explicit_categories:
            if cat not in ordered:
                ordered.append(cat)
        return tuple(ordered)

    seen_categories = {opt.category for opt in options if opt.city_id == traveler.destination_city_id}
    resolved: list[ServiceCategory] = []
    for cat in ServiceCategory:
        if cat == ServiceCategory.DAY_TRIP and not traveler.include_day_trips:
            continue
        if cat in seen_categories:
            resolved.append(cat)
    return tuple(resolved)


def build_audit_prompt(
    traveler: TravelerProfile,
    options: Sequence[ServiceOption],
    *,
    categories: Sequence[ServiceCategory] | None = None,
    city: City | None = None,
) -> str:
    """Build a deterministic prompt from traveler/device profile and closed city catalog."""
    city_options = [opt for opt in options if opt.city_id == traveler.destination_city_id]
    resolved_categories = _resolve_audit_categories(city_options, traveler, categories)

    city_label = (
        f"{city.name} ({traveler.destination_city_id}, {city.local_currency})"
        if city is not None
        else traveler.destination_city_id
    )
    tolerance_str = (
        traveler.friction_tolerance.value
        if hasattr(traveler.friction_tolerance, "value")
        else str(traveler.friction_tolerance)
    )

    lines: list[str] = [
        "You are auditing travel options for a traveler.",
        "Select ONE option id (or null) per category from the closed catalog below.",
        "",
        "Traveler Profile:",
        f"- city: {city_label}",
        f"- trip_duration_days: {traveler.trip_duration_days}",
        f"- has_local_id: {str(traveler.has_local_id).lower()}",
        f"- target_data_gb: {traveler.target_data_gb}",
        f"- friction_tolerance: {tolerance_str}",
        f"- supports_physical_sim: {str(traveler.device_profile.supports_physical_sim).lower()}",
        f"- supports_esim: {str(traveler.device_profile.supports_esim).lower()}",
        f"- include_day_trips: {str(traveler.include_day_trips).lower()}",
        f"- dining_preference: {traveler.dining_preference.value}",
        f"- payment_method_preference: {traveler.payment_method_preference.value}",
        "",
        "Closed Catalog (option_id | name | attributes):",
    ]

    for category in resolved_categories:
        lines.append(f"[{category.value}]")
        cat_opts = sorted(
            (opt for opt in city_options if opt.category == category),
            key=lambda opt: opt.id,
        )
        if not cat_opts:
            lines.append("  (none)")
            continue
        for opt in cat_opts:
            attrs = [
                f"sim_type={opt.sim_type.value}",
                f"requires_local_id={str(opt.requires_local_id).lower()}",
                f"requires_international_card={str(opt.requires_international_card).lower()}",
            ]
            if opt.data_quota_gb is not None:
                attrs.append(f"data_quota_gb={opt.data_quota_gb}")
            lines.append(f"  - {opt.id} | {opt.name} | {', '.join(attrs)}")

    expected_keys = ", ".join(f'"{cat.value}"' for cat in resolved_categories)
    lines.extend(
        [
            "",
            "Output Contract:",
            f"- Reply ONLY with a single JSON object containing exact keys: {expected_keys}.",
            "- Map each category key to ONE option id string from that category above, or null.",
            "- Do not include markdown fences, comments, or any text outside the JSON object.",
        ]
    )
    return "\n".join(lines)


def parse_and_validate_reply(
    raw_reply: str,
    *,
    catalog_options: Sequence[ServiceOption],
    expected_categories: Sequence[ServiceCategory],
    city_id: str,
) -> ParsedRecommendation:
    """Strictly parse JSON reply and validate every selection against the closed catalog."""
    if not isinstance(raw_reply, str) or not raw_reply.strip():
        return ParsedRecommendation(
            raw_reply=raw_reply if isinstance(raw_reply, str) else "",
            is_valid=False,
            selections=MappingProxyType({}),
            errors=("Reply is empty or not a string",),
        )

    try:
        parsed = json.loads(raw_reply)
    except json.JSONDecodeError as exc:
        return ParsedRecommendation(
            raw_reply=raw_reply,
            is_valid=False,
            selections=MappingProxyType({}),
            errors=(f"Reply is not valid JSON: {exc.msg}",),
        )

    if not isinstance(parsed, dict):
        return ParsedRecommendation(
            raw_reply=raw_reply,
            is_valid=False,
            selections=MappingProxyType({}),
            errors=(f"Reply JSON root must be an object, got {type(parsed).__name__}",),
        )

    expected_keys = {cat.value: cat for cat in expected_categories}
    actual_keys = set(parsed.keys())
    errors: list[str] = []

    missing_keys = sorted(set(expected_keys) - actual_keys)
    extra_keys = sorted(actual_keys - set(expected_keys))
    for key in missing_keys:
        errors.append(f"Missing required category key '{key}'")
    for key in extra_keys:
        errors.append(f"Unknown category key '{key}'")

    option_by_id: dict[str, ServiceOption] = {
        opt.id: opt for opt in catalog_options if opt.city_id == city_id
    }
    selections: dict[ServiceCategory, ServiceOption | None] = {}

    for cat in expected_categories:
        if cat.value not in parsed:
            continue
        raw_val = parsed[cat.value]
        if raw_val is None:
            selections[cat] = None
            continue
        if not isinstance(raw_val, str):
            errors.append(
                f"Category '{cat.value}' must map to an option id string or null, "
                f"got {type(raw_val).__name__}"
            )
            continue
        option = option_by_id.get(raw_val)
        if option is None:
            errors.append(
                f"Unknown option id '{raw_val}' for category '{cat.value}' in city '{city_id}'"
            )
            continue
        if option.category != cat:
            errors.append(
                f"Option '{raw_val}' belongs to category '{option.category.value}', "
                f"not '{cat.value}'"
            )
            continue
        selections[cat] = option

    if errors:
        return ParsedRecommendation(
            raw_reply=raw_reply,
            is_valid=False,
            selections=MappingProxyType({}),
            errors=tuple(errors),
        )

    return ParsedRecommendation(
        raw_reply=raw_reply,
        is_valid=True,
        selections=MappingProxyType(selections),
        errors=(),
    )


def _impute_unmapped_category(
    category: ServiceCategory,
    *,
    traveler: TravelerProfile,
    catalog_options: Sequence[ServiceOption] | None,
    zero_friction: TripScenario,
    local_optimized: TripScenario,
) -> tuple[Decimal, Decimal, Decimal] | None:
    """Return (avg_usd, avg_local, avg_friction) across compatible options, or None."""
    if catalog_options is not None:
        candidates = [
            opt
            for opt in catalog_options
            if opt.city_id == traveler.destination_city_id and opt.category == category
        ]
        compatible = apply_hard_filters(candidates, traveler).eligible
        if not compatible:
            return None
        criteria = compute_option_criteria(compatible, traveler)
        count = Decimal(len(criteria))
        avg_usd = sum((c.total_cost_usd for c in criteria), start=_ZERO) / count
        avg_local = sum((c.total_cost_local for c in criteria), start=_ZERO) / count
        avg_friction = sum((c.friction_score for c in criteria), start=_ZERO) / count
        return avg_usd, avg_local, avg_friction

    baseline_choices = [
        choice
        for choice in (
            zero_friction.choice_for(category),
            local_optimized.choice_for(category),
        )
        if choice is not None
    ]
    if not baseline_choices:
        return None
    count = Decimal(len(baseline_choices))
    avg_usd = sum((c.total_cost_usd for c in baseline_choices), start=_ZERO) / count
    avg_local = sum((c.total_cost_local for c in baseline_choices), start=_ZERO) / count
    avg_friction = sum((c.friction_score for c in baseline_choices), start=_ZERO) / count
    return avg_usd, avg_local, avg_friction


def score_recommendation(
    selections: Mapping[ServiceCategory, ServiceOption | None],
    *,
    traveler: TravelerProfile,
    zero_friction: TripScenario,
    local_optimized: TripScenario,
    catalog_options: Sequence[ServiceOption] | None = None,
    penalty_handoff: NumericInput = _ZERO,
    incompatible_pairs: Collection[tuple[str, str]] = (),
) -> RecommendationScore:
    """Evaluate feasibility via hard filters and compute exact cost/friction/overpayment.

    Per engine-spec.md section 5.2, a missing/unclassifiable (null) recommendation for
    a category with compatible options is flagged UNMAPPED_RECOMMENDATION and charged
    the category's average cost and friction over compatible options.
    """
    infeasibility_reasons: dict[ServiceCategory, tuple[RejectionReason, ...]] = {}
    selected_options: list[ServiceOption] = []
    null_categories: list[ServiceCategory] = []
    unmapped_categories: list[ServiceCategory] = []
    imputed_usd = _ZERO
    imputed_local = _ZERO
    imputed_frictions: list[Decimal] = []

    for cat, opt in selections.items():
        if opt is None:
            null_categories.append(cat)
            imputed = _impute_unmapped_category(
                cat,
                traveler=traveler,
                catalog_options=catalog_options,
                zero_friction=zero_friction,
                local_optimized=local_optimized,
            )
            if imputed is not None:
                unmapped_categories.append(cat)
                cat_usd, cat_local, cat_friction = imputed
                imputed_usd += cat_usd
                imputed_local += cat_local
                imputed_frictions.append(cat_friction)
            continue
        selected_options.append(opt)
        other_options = [
            other
            for other_cat, other in selections.items()
            if other is not None and other_cat != cat
        ]
        reasons = evaluate_hard_filters(
            opt,
            traveler,
            selected_options=other_options,
            incompatible_pairs=incompatible_pairs,
        )
        if reasons:
            infeasibility_reasons[cat] = reasons

    selected_frictions: list[Decimal] = []
    if selected_options:
        criteria_list = compute_option_criteria(selected_options, traveler)
        selected_usd = sum((c.total_cost_usd for c in criteria_list), start=_ZERO)
        selected_local = sum((c.total_cost_local for c in criteria_list), start=_ZERO)
        selected_frictions = [c.friction_score for c in criteria_list]
    else:
        selected_usd = _ZERO
        selected_local = _ZERO

    total_usd = selected_usd + imputed_usd
    total_local = selected_local + imputed_local
    all_frictions = [*selected_frictions, *imputed_frictions]
    total_friction = sum(all_frictions, start=_ZERO)

    if selected_options and not imputed_frictions:
        agg_friction = scenario_friction_score(
            selected_options,
            penalty_handoff=penalty_handoff,
        )
    elif all_frictions:
        penalty = to_decimal(penalty_handoff, "penalty_handoff")
        if penalty < _ZERO:
            raise ValueError(f"penalty_handoff must be non-negative, got {penalty}")
        mean_friction = total_friction / Decimal(len(all_frictions))
        agg_friction = max(MIN_FRICTION_SCORE, min(MAX_FRICTION_SCORE, mean_friction + penalty))
    else:
        agg_friction = _ZERO

    over_local_usd = total_usd - local_optimized.total_cost_usd
    over_local_clp = total_local - local_optimized.total_cost_clp
    over_local_pct = (
        (over_local_usd / local_optimized.total_cost_usd) * _HUNDRED
        if local_optimized.total_cost_usd > _ZERO
        else _ZERO
    )
    extra_friction_local = agg_friction - local_optimized.friction_score

    over_zero_usd = total_usd - zero_friction.total_cost_usd
    over_zero_clp = total_local - zero_friction.total_cost_clp
    over_zero_pct = (
        (over_zero_usd / zero_friction.total_cost_usd) * _HUNDRED
        if zero_friction.total_cost_usd > _ZERO
        else _ZERO
    )
    extra_friction_zero = agg_friction - zero_friction.friction_score

    flags: tuple[str, ...] = (UNMAPPED_RECOMMENDATION_FLAG,) if unmapped_categories else ()

    return RecommendationScore(
        selections=MappingProxyType(dict(selections)),
        selected_options=tuple(selected_options),
        null_categories=tuple(null_categories),
        is_feasible=not infeasibility_reasons,
        infeasibility_reasons=MappingProxyType(infeasibility_reasons),
        total_cost_usd=total_usd,
        total_cost_local=total_local,
        total_cost_clp=total_local,
        friction_score=agg_friction,
        total_friction_score=total_friction,
        overpayment_vs_local_usd=over_local_usd,
        overpayment_vs_local_clp=over_local_clp,
        overpayment_vs_local_pct=over_local_pct,
        extra_friction_vs_local=extra_friction_local,
        overpayment_vs_zero_friction_usd=over_zero_usd,
        overpayment_vs_zero_friction_clp=over_zero_clp,
        overpayment_vs_zero_friction_pct=over_zero_pct,
        extra_friction_vs_zero_friction=extra_friction_zero,
        unmapped_categories=tuple(unmapped_categories),
        flags=flags,
    )


def _resolve_salts(
    assistant_name: str,
    replications: int,
    salts: Sequence[str] | None,
) -> tuple[str, ...]:
    if isinstance(replications, bool) or not isinstance(replications, int) or replications < 1:
        raise ValueError(f"replications must be an int >= 1, got {replications!r}")

    if salts is None:
        return tuple(f"{assistant_name}:rep-{idx}" for idx in range(replications))

    resolved = tuple(salts)
    if len(resolved) != replications:
        raise ValueError(
            f"salts length ({len(resolved)}) must match replications ({replications})"
        )
    if len(set(resolved)) != len(resolved):
        raise ValueError("salts must be distinct across replications")
    return resolved


def audit_assistant(
    assistant_name: str,
    assistant: AssistantPort,
    *,
    prompt: str,
    traveler: TravelerProfile,
    catalog_options: Sequence[ServiceOption],
    expected_categories: Sequence[ServiceCategory],
    zero_friction: TripScenario,
    local_optimized: TripScenario,
    replications: int = 5,
    salts: Sequence[str] | None = None,
    penalty_handoff: NumericInput = _ZERO,
    incompatible_pairs: Collection[tuple[str, str]] = (),
) -> AssistantAuditSummary:
    """Run N salted replications for one assistant and aggregate rates and 95% CIs."""
    resolved_salts = _resolve_salts(assistant_name, replications, salts)
    rep_results: list[ReplicationAuditResult] = []
    valid_scores: list[RecommendationScore] = []

    for idx, salt in enumerate(resolved_salts):
        raw_reply = assistant.ask(prompt, salt)
        parsed = parse_and_validate_reply(
            raw_reply,
            catalog_options=catalog_options,
            expected_categories=expected_categories,
            city_id=traveler.destination_city_id,
        )
        if not parsed.is_valid:
            rep_results.append(
                ReplicationAuditResult(
                    replication_index=idx,
                    salt=salt,
                    raw_reply=raw_reply,
                    is_valid=False,
                    is_feasible=False,
                    validation_errors=parsed.errors,
                    score=None,
                )
            )
            continue

        scored = score_recommendation(
            parsed.selections,
            traveler=traveler,
            zero_friction=zero_friction,
            local_optimized=local_optimized,
            catalog_options=catalog_options,
            penalty_handoff=penalty_handoff,
            incompatible_pairs=incompatible_pairs,
        )
        valid_scores.append(scored)
        rep_results.append(
            ReplicationAuditResult(
                replication_index=idx,
                salt=salt,
                raw_reply=raw_reply,
                is_valid=True,
                is_feasible=scored.is_feasible,
                validation_errors=(),
                score=scored,
            )
        )

    total_count = len(rep_results)
    valid_count = len(valid_scores)
    invalid_count = total_count - valid_count
    feasible_scores = [item for item in valid_scores if item.is_feasible]
    feasible_count = len(feasible_scores)
    infeasible_count = valid_count - feasible_count

    validity_rate = Decimal(valid_count) / Decimal(total_count)
    infeasibility_rate = (
        Decimal(infeasible_count) / Decimal(valid_count) if valid_count > 0 else _ZERO
    )

    return AssistantAuditSummary(
        assistant_name=assistant_name,
        replications=tuple(rep_results),
        total_replications=total_count,
        valid_count=valid_count,
        invalid_count=invalid_count,
        feasible_count=feasible_count,
        infeasible_count=infeasible_count,
        validity_rate=validity_rate,
        infeasibility_rate=infeasibility_rate,
        total_cost_usd=compute_confidence_interval_95(
            [s.total_cost_usd for s in feasible_scores]
        ),
        total_cost_clp=compute_confidence_interval_95(
            [s.total_cost_clp for s in feasible_scores]
        ),
        friction_score=compute_confidence_interval_95(
            [s.friction_score for s in feasible_scores]
        ),
        overpayment_vs_local_usd=compute_confidence_interval_95(
            [s.overpayment_vs_local_usd for s in feasible_scores]
        ),
        overpayment_vs_local_clp=compute_confidence_interval_95(
            [s.overpayment_vs_local_clp for s in feasible_scores]
        ),
        overpayment_vs_local_pct=compute_confidence_interval_95(
            [s.overpayment_vs_local_pct for s in feasible_scores]
        ),
        extra_friction_vs_local=compute_confidence_interval_95(
            [s.extra_friction_vs_local for s in feasible_scores]
        ),
        overpayment_vs_zero_friction_usd=compute_confidence_interval_95(
            [s.overpayment_vs_zero_friction_usd for s in feasible_scores]
        ),
        overpayment_vs_zero_friction_clp=compute_confidence_interval_95(
            [s.overpayment_vs_zero_friction_clp for s in feasible_scores]
        ),
        overpayment_vs_zero_friction_pct=compute_confidence_interval_95(
            [s.overpayment_vs_zero_friction_pct for s in feasible_scores]
        ),
        extra_friction_vs_zero_friction=compute_confidence_interval_95(
            [s.extra_friction_vs_zero_friction for s in feasible_scores]
        ),
    )


def run_audit(
    repository: OptionRepository,
    traveler: TravelerProfile,
    assistants: Mapping[str, AssistantPort],
    *,
    replications: int = 5,
    salts_by_assistant: Mapping[str, Sequence[str]] | None = None,
    categories: Sequence[ServiceCategory] | None = None,
    penalty_handoff: NumericInput = _ZERO,
    incompatible_pairs: Collection[tuple[str, str]] = (),
) -> AuditReport:
    """Run the full AI-assistant audit pipeline against the deterministic simulator."""
    catalog_options = tuple(repository.list_options(traveler.destination_city_id))
    audit_categories = _resolve_audit_categories(catalog_options, traveler, categories)
    sim_result = simulate(
        repository,
        traveler=traveler,
        categories=audit_categories,
        penalty_handoff=penalty_handoff,
        incompatible_pairs=incompatible_pairs,
    )
    prompt = build_audit_prompt(
        traveler,
        catalog_options,
        categories=audit_categories,
        city=sim_result.city,
    )

    summaries: dict[str, AssistantAuditSummary] = {}
    for name, assistant in assistants.items():
        custom_salts = salts_by_assistant.get(name) if salts_by_assistant is not None else None
        summaries[name] = audit_assistant(
            name,
            assistant,
            prompt=prompt,
            traveler=traveler,
            catalog_options=catalog_options,
            expected_categories=audit_categories,
            zero_friction=sim_result.zero_friction,
            local_optimized=sim_result.local_optimized,
            replications=replications,
            salts=custom_salts,
            penalty_handoff=penalty_handoff,
            incompatible_pairs=incompatible_pairs,
        )

    return AuditReport(
        city_id=sim_result.city_id,
        city_name=sim_result.city.name if sim_result.city is not None else None,
        local_currency=sim_result.city.local_currency if sim_result.city is not None else None,
        traveler=sim_result.traveler,
        categories=audit_categories,
        prompt=prompt,
        zero_friction_baseline=sim_result.zero_friction,
        local_optimized_baseline=sim_result.local_optimized,
        assistants=MappingProxyType(summaries),
    )


def _fmt_ci(ci: ConfidenceInterval | None, *, unit: str = "", decimals: int = 2) -> str:
    if ci is None:
        return "n/a"
    fmt = f"{{:.{decimals}f}}"
    mean_s = fmt.format(ci.mean)
    low_s = fmt.format(ci.lower)
    high_s = fmt.format(ci.upper)
    suffix = f" {unit}" if unit else ""
    return f"{mean_s}{suffix} (95% CI [{low_s}, {high_s}])"


def format_audit_report_text(report: AuditReport) -> str:
    """Format an AuditReport as a deterministic human-readable text report."""
    city_label = f"{report.city_name} ({report.city_id})" if report.city_name else report.city_id
    local_curr = report.local_currency or "CLP"
    lines: list[str] = [
        f"AI Assistant Audit Report - {city_label}",
        (
            f"Traveler: days={report.traveler.trip_duration_days}, "
            f"has_local_id={report.traveler.has_local_id}, "
            f"target_data_gb={report.traveler.target_data_gb}, "
            f"physical_sim={report.traveler.device_profile.supports_physical_sim}, "
            f"esim={report.traveler.device_profile.supports_esim}"
        ),
        (
            f"Baseline Local Optimized: "
            f"${report.local_optimized_baseline.total_cost_usd:.2f} USD / "
            f"{report.local_optimized_baseline.total_cost_clp:.0f} {local_curr} | "
            f"friction={report.local_optimized_baseline.friction_score:.2f}"
        ),
        (
            f"Baseline Zero Friction:   "
            f"${report.zero_friction_baseline.total_cost_usd:.2f} USD / "
            f"{report.zero_friction_baseline.total_cost_clp:.0f} {local_curr} | "
            f"friction={report.zero_friction_baseline.friction_score:.2f}"
        ),
        "",
    ]

    for name, summary in report.assistants.items():
        val_pct = summary.validity_rate * _HUNDRED
        inf_pct = summary.infeasibility_rate * _HUNDRED
        lines.extend(
            [
                f"Assistant: {name}",
                (
                    f"  Validity: {summary.valid_count}/{summary.total_replications} "
                    f"({val_pct:.1f}%) | "
                    f"Infeasible (of valid): {summary.infeasible_count}/{summary.valid_count} "
                    f"({inf_pct:.1f}%)"
                ),
                f"  Cost (USD): {_fmt_ci(summary.total_cost_usd, unit='USD')}",
                (
                    f"  Cost ({local_curr}): "
                    f"{_fmt_ci(summary.total_cost_clp, unit=local_curr, decimals=0)}"
                ),
                f"  Friction:   {_fmt_ci(summary.friction_score)}",
                (
                    f"  Vs Local Optimized: "
                    f"overpay={_fmt_ci(summary.overpayment_vs_local_usd, unit='USD')} | "
                    f"{_fmt_ci(summary.overpayment_vs_local_clp, unit=local_curr, decimals=0)} | "
                    f"extra_friction={_fmt_ci(summary.extra_friction_vs_local)}"
                ),
                (
                    f"  Vs Zero Friction:   "
                    f"overpay={_fmt_ci(summary.overpayment_vs_zero_friction_usd, unit='USD')} | "
                    f"{_fmt_ci(summary.overpayment_vs_zero_friction_clp, unit=local_curr, decimals=0)} | "
                    f"extra_friction={_fmt_ci(summary.extra_friction_vs_zero_friction)}"
                ),
            ]
        )

    return "\n".join(lines)


def format_audit_report_json(report: AuditReport, *, indent: int | None = 2) -> str:
    """Format an AuditReport as deterministic JSON."""
    return json.dumps(report.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False)


class AuditAIAssistantsUseCase:
    """Application use case wrapping `run_audit` with an injected OptionRepository."""

    def __init__(self, repository: OptionRepository) -> None:
        self._repository = repository

    @property
    def repository(self) -> OptionRepository:
        """Return the underlying OptionRepository port."""
        return self._repository

    def execute(
        self,
        traveler: TravelerProfile,
        assistants: Mapping[str, AssistantPort],
        *,
        replications: int = 5,
        salts_by_assistant: Mapping[str, Sequence[str]] | None = None,
        categories: Sequence[ServiceCategory] | None = None,
        penalty_handoff: NumericInput = _ZERO,
        incompatible_pairs: Collection[tuple[str, str]] = (),
    ) -> AuditReport:
        """Run the AI-assistant audit against the configured OptionRepository."""
        return run_audit(
            self._repository,
            traveler,
            assistants,
            replications=replications,
            salts_by_assistant=salts_by_assistant,
            categories=categories,
            penalty_handoff=penalty_handoff,
            incompatible_pairs=incompatible_pairs,
        )

    run = execute
    __call__ = execute


__all__ = [
    "UNMAPPED_RECOMMENDATION_FLAG",
    "AssistantAuditSummary",
    "AuditAIAssistantsUseCase",
    "AuditReport",
    "ConfidenceInterval",
    "ParsedRecommendation",
    "RecommendationScore",
    "ReplicationAuditResult",
    "audit_assistant",
    "build_audit_prompt",
    "compute_confidence_interval_95",
    "format_audit_report_json",
    "format_audit_report_text",
    "parse_and_validate_reply",
    "run_audit",
    "score_recommendation",
]
