"""Deterministic scenario builder per docs/travel-simulator/engine-spec.md."""
from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from travel_sim.application.filters import (
    DEFAULT_BALANCED_EFFICIENCY_THRESHOLD_USD,
    DEFAULT_BALANCED_MAX_FRICTION,
    HardFilterResult,
    OptionCriteria,
    ScoredOption,
    apply_hard_filters,
    apply_soft_filters,
    are_options_compatible,
    local_optimized_scorer,
    make_balanced_substitution_predicate,
    zero_friction_scorer,
)
from travel_sim.domain import (
    ScenarioType,
    ServiceCategory,
    ServiceOption,
    TravelerProfile,
    scenario_friction_score,
)
from travel_sim.domain.value_objects import NumericInput, to_decimal

_HUNDRED = Decimal(100)
_ONE = Decimal(1)
_ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class ScenarioSavings:
    """Exact monetary savings and friction trade-off vs the Zero Friction baseline."""

    scenario_type: ScenarioType
    baseline_cost_usd: Decimal
    scenario_cost_usd: Decimal
    savings_usd: Decimal
    baseline_cost_local: Decimal
    scenario_cost_local: Decimal
    savings_local: Decimal
    savings_clp: Decimal
    savings_percentage: Decimal
    friction_delta: Decimal
    total_friction_delta: Decimal
    extra_time_minutes: int
    efficiency_ratio: Decimal

    @property
    def delta_cost_usd(self) -> Decimal:
        """Alias for savings_usd per engine-spec.md section 4.1."""
        return self.savings_usd

    @property
    def delta_cost_local(self) -> Decimal:
        """Alias for savings_local per engine-spec.md section 4.1."""
        return self.savings_local

    @property
    def delta_cost_clp(self) -> Decimal:
        """Alias for savings_clp per engine-spec.md section 4.1."""
        return self.savings_clp

    @property
    def delta_friction(self) -> Decimal:
        """Alias for friction_delta per engine-spec.md section 4.2."""
        return self.friction_delta

    @property
    def savings_pct(self) -> Decimal:
        """Alias for savings_percentage."""
        return self.savings_percentage


@dataclass(frozen=True, slots=True)
class CategoryChoice:
    """Selected option and computed metrics for a single category and scenario."""

    category: ServiceCategory
    scenario_type: ScenarioType
    option: ServiceOption
    criteria: OptionCriteria
    score: Decimal
    total_cost_usd: Decimal
    total_cost_local: Decimal
    total_cost_clp: Decimal
    daily_cost_usd: Decimal
    friction_score: Decimal
    setup_time_minutes: int
    extra_time_minutes: int
    savings_usd: Decimal
    savings_local: Decimal
    savings_clp: Decimal
    unverified: bool = False

    @property
    def option_id(self) -> str:
        """Unique identifier of the selected service option."""
        return self.option.id

    @property
    def is_verified(self) -> bool:
        """Return True if the selected service option has verified metadata."""
        return not self.unverified


@dataclass(frozen=True, slots=True)
class CategoryScenarioBundle:
    """The 3 scenario choices (Zero Friction, Balanced, Local Optimized) for one category."""

    category: ServiceCategory
    zero_friction: CategoryChoice | None
    balanced: CategoryChoice | None
    local_optimized: CategoryChoice | None
    has_compatible_option: bool
    eligible_count: int
    status_message: str | None = None

    @property
    def is_available(self) -> bool:
        """Return True when at least one compatible option exists for this category."""
        return self.has_compatible_option

    def choice_for(self, scenario_type: ScenarioType) -> CategoryChoice | None:
        """Return the category choice for the given scenario archetype."""
        if scenario_type == ScenarioType.ZERO_FRICTION:
            return self.zero_friction
        if scenario_type == ScenarioType.BALANCED:
            return self.balanced
        if scenario_type == ScenarioType.LOCAL_OPTIMIZED:
            return self.local_optimized
        raise KeyError(f"Unknown ScenarioType: {scenario_type!r}")

    def as_dict(self) -> dict[ScenarioType, CategoryChoice | None]:
        """Return mapping from ScenarioType to CategoryChoice (or None)."""
        return {
            ScenarioType.ZERO_FRICTION: self.zero_friction,
            ScenarioType.BALANCED: self.balanced,
            ScenarioType.LOCAL_OPTIMIZED: self.local_optimized,
        }

    def __getitem__(self, scenario_type: ScenarioType) -> CategoryChoice | None:
        return self.choice_for(scenario_type)


@dataclass(frozen=True, slots=True)
class TripScenario:
    """Whole-trip aggregated scenario across all evaluated service categories."""

    scenario_type: ScenarioType
    choices: tuple[CategoryChoice, ...]
    choices_by_category: Mapping[ServiceCategory, CategoryChoice | None]
    total_cost_usd: Decimal
    total_cost_local: Decimal
    total_cost_clp: Decimal
    daily_cost_usd: Decimal
    daily_cost_local: Decimal
    daily_cost_clp: Decimal
    friction_score: Decimal
    total_friction_score: Decimal
    total_setup_time_minutes: int
    extra_time_minutes: int
    savings: ScenarioSavings
    missing_categories: tuple[ServiceCategory, ...]
    unverified: bool = False
    unverified_option_ids: tuple[str, ...] = ()

    @property
    def selected_options(self) -> tuple[ServiceOption, ...]:
        """Ordered tuple of selected ServiceOption entities in this scenario."""
        return tuple(choice.option for choice in self.choices)

    @property
    def options(self) -> tuple[ServiceOption, ...]:
        """Alias for selected_options."""
        return self.selected_options

    @property
    def average_friction_score(self) -> Decimal:
        """Normalized scenario friction score in [0, 100]."""
        return self.friction_score

    @property
    def scenario_friction_score(self) -> Decimal:
        """Alias for friction_score per data-model.md section 5.3."""
        return self.friction_score

    @property
    def total_extra_time_minutes(self) -> int:
        """Total extra setup/wait minutes compared with Zero Friction."""
        return self.extra_time_minutes

    @property
    def savings_usd(self) -> Decimal:
        """Total USD saved compared with the Zero Friction scenario."""
        return self.savings.savings_usd

    @property
    def savings_local(self) -> Decimal:
        """Total local currency saved compared with the Zero Friction scenario."""
        return self.savings.savings_local

    @property
    def savings_clp(self) -> Decimal:
        """Total CLP saved compared with the Zero Friction scenario."""
        return self.savings.savings_clp

    @property
    def savings_percentage(self) -> Decimal:
        """Percentage USD saved compared with the Zero Friction scenario."""
        return self.savings.savings_percentage

    @property
    def unavailable_categories(self) -> tuple[ServiceCategory, ...]:
        """Alias for missing_categories."""
        return self.missing_categories

    @property
    def has_unverified_options(self) -> bool:
        """Return True if any selected option in this scenario is unverified."""
        return bool(self.unverified_option_ids)

    def choice_for(self, category: ServiceCategory) -> CategoryChoice | None:
        """Return the selected CategoryChoice for category, or None if unavailable."""
        return self.choices_by_category.get(category)


@dataclass(frozen=True, slots=True)
class ScenarioBuildResult:
    """Complete deterministic output of the 3-scenario builder."""

    categories: tuple[ServiceCategory, ...]
    category_scenarios: Mapping[ServiceCategory, CategoryScenarioBundle]
    scenarios: Mapping[ScenarioType, TripScenario]
    zero_friction: TripScenario
    balanced: TripScenario
    local_optimized: TripScenario
    savings: Mapping[ScenarioType, ScenarioSavings]
    missing_categories: tuple[ServiceCategory, ...]
    unverified: bool = False
    unverified_option_ids: tuple[str, ...] = ()

    @property
    def unavailable_categories(self) -> tuple[ServiceCategory, ...]:
        """Categories that had no compatible option after filtering."""
        return self.missing_categories

    @property
    def has_unverified_options(self) -> bool:
        """Return True if any selected option across built scenarios is unverified."""
        return self.unverified

    def scenario_for(self, scenario_type: ScenarioType) -> TripScenario:
        """Return the TripScenario for scenario_type."""
        return self.scenarios[scenario_type]

    def __getitem__(self, scenario_type: ScenarioType) -> TripScenario:
        return self.scenarios[scenario_type]


def _is_option_unverified(option: ServiceOption, unverified_ids: Collection[str]) -> bool:
    if option.id in unverified_ids:
        return True
    return getattr(option, "last_verified_at", None) is None


def _build_category_choice(
    *,
    category: ServiceCategory,
    scenario_type: ScenarioType,
    scored: ScoredOption,
    baseline_criteria: OptionCriteria,
    unverified_ids: Collection[str],
) -> CategoryChoice:
    criteria = scored.criteria
    option = criteria.option
    savings_usd = baseline_criteria.total_cost_usd - criteria.total_cost_usd
    savings_local = baseline_criteria.total_cost_local - criteria.total_cost_local
    return CategoryChoice(
        category=category,
        scenario_type=scenario_type,
        option=option,
        criteria=criteria,
        score=scored.score,
        total_cost_usd=criteria.total_cost_usd,
        total_cost_local=criteria.total_cost_local,
        total_cost_clp=criteria.total_cost_local,
        daily_cost_usd=criteria.daily_cost_usd,
        friction_score=criteria.friction_score,
        setup_time_minutes=option.setup_time_minutes,
        extra_time_minutes=criteria.extra_time_minutes,
        savings_usd=savings_usd,
        savings_local=savings_local,
        savings_clp=savings_local,
        unverified=_is_option_unverified(option, unverified_ids),
    )


def calculate_scenario_savings(
    *,
    scenario_type: ScenarioType,
    baseline_cost_usd: NumericInput,
    scenario_cost_usd: NumericInput,
    baseline_cost_local: NumericInput,
    scenario_cost_local: NumericInput,
    baseline_friction_score: NumericInput,
    scenario_friction_score_val: NumericInput,
    baseline_total_friction_score: NumericInput = _ZERO,
    scenario_total_friction_score: NumericInput = _ZERO,
    extra_time_minutes: int = 0,
) -> ScenarioSavings:
    """Compute exact savings and friction trade-off metrics per engine-spec.md section 4."""
    base_usd = to_decimal(baseline_cost_usd, "baseline_cost_usd")
    scen_usd = to_decimal(scenario_cost_usd, "scenario_cost_usd")
    base_local = to_decimal(baseline_cost_local, "baseline_cost_local")
    scen_local = to_decimal(scenario_cost_local, "scenario_cost_local")
    base_friction = to_decimal(baseline_friction_score, "baseline_friction_score")
    scen_friction = to_decimal(scenario_friction_score_val, "scenario_friction_score_val")
    base_total_f = to_decimal(baseline_total_friction_score, "baseline_total_friction_score")
    scen_total_f = to_decimal(scenario_total_friction_score, "scenario_total_friction_score")

    savings_usd = base_usd - scen_usd
    savings_local = base_local - scen_local
    savings_pct = (savings_usd / base_usd) * _HUNDRED if base_usd > _ZERO else _ZERO
    friction_delta = scen_friction - base_friction
    total_friction_delta = scen_total_f - base_total_f
    denominator = max(_ONE, friction_delta)
    efficiency_ratio = savings_usd / denominator

    return ScenarioSavings(
        scenario_type=scenario_type,
        baseline_cost_usd=base_usd,
        scenario_cost_usd=scen_usd,
        savings_usd=savings_usd,
        baseline_cost_local=base_local,
        scenario_cost_local=scen_local,
        savings_local=savings_local,
        savings_clp=savings_local,
        savings_percentage=savings_pct,
        friction_delta=friction_delta,
        total_friction_delta=total_friction_delta,
        extra_time_minutes=extra_time_minutes,
        efficiency_ratio=efficiency_ratio,
    )


def build_category_scenarios(
    category: ServiceCategory,
    options: Sequence[ServiceOption],
    traveler: TravelerProfile,
    *,
    efficiency_threshold_usd: NumericInput = DEFAULT_BALANCED_EFFICIENCY_THRESHOLD_USD,
    max_balanced_friction: NumericInput = DEFAULT_BALANCED_MAX_FRICTION,
    unverified_option_ids: Collection[str] = (),
) -> CategoryScenarioBundle:
    """Build Cero Friccion, Balanceado, and Optimizado Local choices for one category.

    Applies hard filters idempotently to options matching `category`. If no eligible
    option remains, returns an unavailable bundle instead of raising an exception.
    Tie-breaking is strictly deterministic by option.id via apply_soft_filters.
    """
    category_candidates = [opt for opt in options if opt.category == category]
    eligible = apply_hard_filters(category_candidates, traveler).eligible

    if not eligible:
        return CategoryScenarioBundle(
            category=category,
            zero_friction=None,
            balanced=None,
            local_optimized=None,
            has_compatible_option=False,
            eligible_count=0,
            status_message=f"No compatible option available for category {category.value}",
        )

    zero_ranked = apply_soft_filters(
        eligible,
        traveler,
        scorer=zero_friction_scorer,
    )
    local_ranked = apply_soft_filters(
        eligible,
        traveler,
        scorer=local_optimized_scorer,
    )

    zero_scored = zero_ranked[0]
    local_scored = local_ranked[0]

    balanced_predicate = make_balanced_substitution_predicate(
        zero_scored.criteria,
        min_usd_per_friction_point=efficiency_threshold_usd,
        max_friction=max_balanced_friction,
    )
    balanced_ranked = apply_soft_filters(
        eligible,
        traveler,
        scorer=local_optimized_scorer,
        predicates=(balanced_predicate,),
    )
    balanced_scored = balanced_ranked[0] if balanced_ranked else zero_scored

    zero_choice = _build_category_choice(
        category=category,
        scenario_type=ScenarioType.ZERO_FRICTION,
        scored=zero_scored,
        baseline_criteria=zero_scored.criteria,
        unverified_ids=unverified_option_ids,
    )
    balanced_choice = _build_category_choice(
        category=category,
        scenario_type=ScenarioType.BALANCED,
        scored=balanced_scored,
        baseline_criteria=zero_scored.criteria,
        unverified_ids=unverified_option_ids,
    )
    local_choice = _build_category_choice(
        category=category,
        scenario_type=ScenarioType.LOCAL_OPTIMIZED,
        scored=local_scored,
        baseline_criteria=zero_scored.criteria,
        unverified_ids=unverified_option_ids,
    )

    return CategoryScenarioBundle(
        category=category,
        zero_friction=zero_choice,
        balanced=balanced_choice,
        local_optimized=local_choice,
        has_compatible_option=True,
        eligible_count=len(eligible),
        status_message=None,
    )


def _resolve_categories(
    all_seen_options: Sequence[ServiceOption],
    traveler: TravelerProfile,
    explicit_categories: Sequence[ServiceCategory] | None,
) -> tuple[ServiceCategory, ...]:
    if explicit_categories is not None:
        ordered: list[ServiceCategory] = []
        for cat in explicit_categories:
            if cat not in ordered:
                ordered.append(cat)
        return tuple(ordered)

    seen_set = {opt.category for opt in all_seen_options}
    resolved: list[ServiceCategory] = []
    for cat in ServiceCategory:
        if cat == ServiceCategory.DAY_TRIP and not traveler.include_day_trips:
            continue
        if cat in seen_set:
            resolved.append(cat)
    return tuple(resolved)


def _select_compatible_for_category(
    category: ServiceCategory,
    eligible_options: Sequence[ServiceOption],
    traveler: TravelerProfile,
    *,
    selected_by_scenario: Mapping[ScenarioType, Sequence[ServiceOption]],
    incompatible_pairs: Collection[tuple[str, str]],
    efficiency_threshold_usd: NumericInput,
    max_balanced_friction: NumericInput,
    unverified_option_ids: Collection[str],
) -> CategoryScenarioBundle:
    has_incompatibilities = bool(incompatible_pairs) or any(
        bool(opt.incompatible_option_ids) for opt in eligible_options
    )
    if not has_incompatibilities:
        return build_category_scenarios(
            category,
            eligible_options,
            traveler,
            efficiency_threshold_usd=efficiency_threshold_usd,
            max_balanced_friction=max_balanced_friction,
            unverified_option_ids=unverified_option_ids,
        )

    def _filter_compatible(scenario_type: ScenarioType) -> list[ServiceOption]:
        prior = selected_by_scenario[scenario_type]
        return [
            opt
            for opt in eligible_options
            if opt.category == category
            and all(
                are_options_compatible(opt, prev, incompatible_pairs=incompatible_pairs)
                for prev in prior
            )
        ]

    zero_pool = _filter_compatible(ScenarioType.ZERO_FRICTION)
    balanced_pool = _filter_compatible(ScenarioType.BALANCED)
    local_pool = _filter_compatible(ScenarioType.LOCAL_OPTIMIZED)

    if not zero_pool or not balanced_pool or not local_pool:
        return CategoryScenarioBundle(
            category=category,
            zero_friction=None,
            balanced=None,
            local_optimized=None,
            has_compatible_option=False,
            eligible_count=0,
            status_message=f"No compatible option available for category {category.value}",
        )

    zero_scored = apply_soft_filters(zero_pool, traveler, scorer=zero_friction_scorer)[0]
    local_scored = apply_soft_filters(local_pool, traveler, scorer=local_optimized_scorer)[0]

    balanced_base_pool = apply_soft_filters(balanced_pool, traveler, scorer=zero_friction_scorer)
    balanced_baseline = balanced_base_pool[0]
    balanced_predicate = make_balanced_substitution_predicate(
        balanced_baseline.criteria,
        min_usd_per_friction_point=efficiency_threshold_usd,
        max_friction=max_balanced_friction,
    )
    balanced_ranked = apply_soft_filters(
        balanced_pool,
        traveler,
        scorer=local_optimized_scorer,
        predicates=(balanced_predicate,),
    )
    balanced_scored = balanced_ranked[0] if balanced_ranked else balanced_baseline

    return CategoryScenarioBundle(
        category=category,
        zero_friction=_build_category_choice(
            category=category,
            scenario_type=ScenarioType.ZERO_FRICTION,
            scored=zero_scored,
            baseline_criteria=zero_scored.criteria,
            unverified_ids=unverified_option_ids,
        ),
        balanced=_build_category_choice(
            category=category,
            scenario_type=ScenarioType.BALANCED,
            scored=balanced_scored,
            baseline_criteria=zero_scored.criteria,
            unverified_ids=unverified_option_ids,
        ),
        local_optimized=_build_category_choice(
            category=category,
            scenario_type=ScenarioType.LOCAL_OPTIMIZED,
            scored=local_scored,
            baseline_criteria=zero_scored.criteria,
            unverified_ids=unverified_option_ids,
        ),
        has_compatible_option=True,
        eligible_count=min(len(zero_pool), len(balanced_pool), len(local_pool)),
        status_message=None,
    )


def _assemble_trip_scenario(
    *,
    scenario_type: ScenarioType,
    categories: Sequence[ServiceCategory],
    category_bundles: Mapping[ServiceCategory, CategoryScenarioBundle],
    traveler: TravelerProfile,
    penalty_handoff: NumericInput,
    baseline_totals: tuple[Decimal, Decimal, Decimal, Decimal] | None,
) -> TripScenario:
    choices: list[CategoryChoice] = []
    choices_by_cat: dict[ServiceCategory, CategoryChoice | None] = {}
    missing: list[ServiceCategory] = []

    for category in categories:
        bundle = category_bundles[category]
        choice = bundle.choice_for(scenario_type)
        choices_by_cat[category] = choice
        if choice is None:
            missing.append(category)
        else:
            choices.append(choice)

    days = Decimal(traveler.trip_duration_days)
    total_usd = sum((c.total_cost_usd for c in choices), start=_ZERO)
    total_local = sum((c.total_cost_local for c in choices), start=_ZERO)
    daily_usd = total_usd / days
    daily_local = total_local / days

    total_friction = sum((c.friction_score for c in choices), start=_ZERO)
    selected_opts = tuple(c.option for c in choices)
    if selected_opts:
        agg_friction = scenario_friction_score(selected_opts, penalty_handoff=penalty_handoff)
    else:
        agg_friction = _ZERO

    total_setup_minutes = sum(c.setup_time_minutes for c in choices)
    extra_minutes = sum(c.extra_time_minutes for c in choices)

    if baseline_totals is None:
        base_usd, base_local, base_agg_f, base_total_f = (
            total_usd,
            total_local,
            agg_friction,
            total_friction,
        )
    else:
        base_usd, base_local, base_agg_f, base_total_f = baseline_totals

    savings = calculate_scenario_savings(
        scenario_type=scenario_type,
        baseline_cost_usd=base_usd,
        scenario_cost_usd=total_usd,
        baseline_cost_local=base_local,
        scenario_cost_local=total_local,
        baseline_friction_score=base_agg_f,
        scenario_friction_score_val=agg_friction,
        baseline_total_friction_score=base_total_f,
        scenario_total_friction_score=total_friction,
        extra_time_minutes=extra_minutes,
    )

    unverified_ids = tuple(c.option.id for c in choices if c.unverified)

    return TripScenario(
        scenario_type=scenario_type,
        choices=tuple(choices),
        choices_by_category=MappingProxyType(choices_by_cat),
        total_cost_usd=total_usd,
        total_cost_local=total_local,
        total_cost_clp=total_local,
        daily_cost_usd=daily_usd,
        daily_cost_local=daily_local,
        daily_cost_clp=daily_local,
        friction_score=agg_friction,
        total_friction_score=total_friction,
        total_setup_time_minutes=total_setup_minutes,
        extra_time_minutes=extra_minutes,
        savings=savings,
        missing_categories=tuple(missing),
        unverified=bool(unverified_ids),
        unverified_option_ids=unverified_ids,
    )


def build_scenarios(
    options: Sequence[ServiceOption] | HardFilterResult,
    traveler: TravelerProfile,
    *,
    categories: Sequence[ServiceCategory] | None = None,
    efficiency_threshold_usd: NumericInput = DEFAULT_BALANCED_EFFICIENCY_THRESHOLD_USD,
    max_balanced_friction: NumericInput = DEFAULT_BALANCED_MAX_FRICTION,
    penalty_handoff: NumericInput = Decimal(0),
    incompatible_pairs: Collection[tuple[str, str]] = (),
    unverified_option_ids: Collection[str] = (),
) -> ScenarioBuildResult:
    """Build Cero Friccion, Balanceado, and Optimizado Local scenarios for the trip.

    Accepts either a sequence of candidate ServiceOptions (applying hard filters
    automatically) or a pre-computed HardFilterResult. Categories with no eligible
    option are recorded in `missing_categories` without raising an exception.
    """
    if isinstance(options, HardFilterResult):
        all_seen: tuple[ServiceOption, ...] = (
            *options.eligible,
            *(r.option for r in options.rejected),
        )
        eligible = options.eligible
    else:
        all_seen = tuple(options)
        eligible = apply_hard_filters(
            all_seen,
            traveler,
            incompatible_pairs=incompatible_pairs,
        ).eligible

    resolved_categories = _resolve_categories(all_seen, traveler, categories)

    selected_by_scenario: dict[ScenarioType, list[ServiceOption]] = {
        ScenarioType.ZERO_FRICTION: [],
        ScenarioType.BALANCED: [],
        ScenarioType.LOCAL_OPTIMIZED: [],
    }
    category_bundles: dict[ServiceCategory, CategoryScenarioBundle] = {}

    for category in resolved_categories:
        bundle = _select_compatible_for_category(
            category,
            eligible,
            traveler,
            selected_by_scenario=selected_by_scenario,
            incompatible_pairs=incompatible_pairs,
            efficiency_threshold_usd=efficiency_threshold_usd,
            max_balanced_friction=max_balanced_friction,
            unverified_option_ids=unverified_option_ids,
        )
        category_bundles[category] = bundle
        if bundle.zero_friction is not None:
            selected_by_scenario[ScenarioType.ZERO_FRICTION].append(bundle.zero_friction.option)
        if bundle.balanced is not None:
            selected_by_scenario[ScenarioType.BALANCED].append(bundle.balanced.option)
        if bundle.local_optimized is not None:
            selected_by_scenario[ScenarioType.LOCAL_OPTIMIZED].append(
                bundle.local_optimized.option
            )

    zero_scenario = _assemble_trip_scenario(
        scenario_type=ScenarioType.ZERO_FRICTION,
        categories=resolved_categories,
        category_bundles=category_bundles,
        traveler=traveler,
        penalty_handoff=penalty_handoff,
        baseline_totals=None,
    )
    baseline_totals = (
        zero_scenario.total_cost_usd,
        zero_scenario.total_cost_local,
        zero_scenario.friction_score,
        zero_scenario.total_friction_score,
    )

    balanced_scenario = _assemble_trip_scenario(
        scenario_type=ScenarioType.BALANCED,
        categories=resolved_categories,
        category_bundles=category_bundles,
        traveler=traveler,
        penalty_handoff=penalty_handoff,
        baseline_totals=baseline_totals,
    )
    local_scenario = _assemble_trip_scenario(
        scenario_type=ScenarioType.LOCAL_OPTIMIZED,
        categories=resolved_categories,
        category_bundles=category_bundles,
        traveler=traveler,
        penalty_handoff=penalty_handoff,
        baseline_totals=baseline_totals,
    )

    scenarios_map: Mapping[ScenarioType, TripScenario] = MappingProxyType(
        {
            ScenarioType.ZERO_FRICTION: zero_scenario,
            ScenarioType.BALANCED: balanced_scenario,
            ScenarioType.LOCAL_OPTIMIZED: local_scenario,
        }
    )
    savings_map: Mapping[ScenarioType, ScenarioSavings] = MappingProxyType(
        {
            ScenarioType.ZERO_FRICTION: zero_scenario.savings,
            ScenarioType.BALANCED: balanced_scenario.savings,
            ScenarioType.LOCAL_OPTIMIZED: local_scenario.savings,
        }
    )

    all_unverified_ids: list[str] = []
    for scen in (zero_scenario, balanced_scenario, local_scenario):
        for opt_id in scen.unverified_option_ids:
            if opt_id not in all_unverified_ids:
                all_unverified_ids.append(opt_id)

    return ScenarioBuildResult(
        categories=resolved_categories,
        category_scenarios=MappingProxyType(category_bundles),
        scenarios=scenarios_map,
        zero_friction=zero_scenario,
        balanced=balanced_scenario,
        local_optimized=local_scenario,
        savings=savings_map,
        missing_categories=zero_scenario.missing_categories,
        unverified=bool(all_unverified_ids),
        unverified_option_ids=tuple(all_unverified_ids),
    )


CategoryScenarios = CategoryScenarioBundle
ScenarioPlan = TripScenario
SimulationScenario = TripScenario
ScenarioEngineResult = ScenarioBuildResult
build_trip_scenarios = build_scenarios

__all__ = [
    "CategoryChoice",
    "CategoryScenarioBundle",
    "CategoryScenarios",
    "ScenarioBuildResult",
    "ScenarioEngineResult",
    "ScenarioPlan",
    "ScenarioSavings",
    "SimulationScenario",
    "TripScenario",
    "build_category_scenarios",
    "build_scenarios",
    "build_trip_scenarios",
    "calculate_scenario_savings",
]
