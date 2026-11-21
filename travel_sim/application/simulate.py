"""Simulation use case orchestrating OptionRepository, hard filters, and scenarios."""
from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType

from travel_sim.application.filters import (
    HardFilterResult,
    RejectedOption,
    apply_hard_filters,
)
from travel_sim.application.ports import OptionRepository
from travel_sim.application.scenarios import (
    CategoryChoice,
    CategoryScenarioBundle,
    ScenarioSavings,
    TripScenario,
    build_scenarios,
)
from travel_sim.domain import (
    City,
    DeviceProfile,
    DiningPreference,
    FreshnessStatus,
    FrictionTolerance,
    PaymentMethodPreference,
    ScenarioType,
    ServiceCategory,
    ServiceOption,
    TravelerProfile,
    freshness_status,
)
from travel_sim.domain.value_objects import NumericInput, to_decimal


@dataclass(frozen=True, slots=True)
class SimulationRequest:
    """Immutable input parameters for running a city travel simulation."""

    city_id: str | None = None
    traveler: TravelerProfile | None = None
    device_profile: DeviceProfile | None = None
    trip_duration_days: int | None = None
    has_local_id: bool | None = None
    target_data_gb: NumericInput | None = None
    friction_tolerance: FrictionTolerance | Decimal | None = None
    include_day_trips: bool | None = None
    dining_preference: DiningPreference | None = None
    payment_method_preference: PaymentMethodPreference | None = None
    traveler_id: str = "traveler-default"
    categories: tuple[ServiceCategory, ...] | None = None
    efficiency_threshold_usd: NumericInput | None = None
    max_balanced_friction: NumericInput | None = None
    penalty_handoff: NumericInput = Decimal(0)
    incompatible_pairs: tuple[tuple[str, str], ...] = ()
    reference_time: datetime | None = None


@dataclass(frozen=True, slots=True)
class ScenarioTotals:
    """Aggregated cost, friction, and time totals for a single scenario."""

    scenario_type: ScenarioType
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


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Immutable result returned by the simulate use case."""

    city_id: str
    city: City | None
    traveler: TravelerProfile
    categories: tuple[ServiceCategory, ...]
    category_scenarios: Mapping[ServiceCategory, CategoryScenarioBundle]
    per_category_choices: Mapping[ServiceCategory, Mapping[ScenarioType, CategoryChoice | None]]
    scenarios: Mapping[ScenarioType, TripScenario]
    zero_friction: TripScenario
    balanced: TripScenario
    local_optimized: TripScenario
    totals: Mapping[ScenarioType, ScenarioTotals]
    savings: Mapping[ScenarioType, ScenarioSavings]
    eligible_options: tuple[ServiceOption, ...]
    rejected_options: tuple[RejectedOption, ...]
    missing_categories: tuple[ServiceCategory, ...]
    unverified: bool
    city_unverified: bool
    unverified_option_ids: tuple[str, ...]
    unverified_options: tuple[ServiceOption, ...]
    city_freshness: FreshnessStatus | None = None
    option_freshness: Mapping[str, FreshnessStatus] = field(
        default_factory=lambda: MappingProxyType({})
    )
    stale_option_ids: tuple[str, ...] = ()
    expired_option_ids: tuple[str, ...] = ()
    stale_options: tuple[ServiceOption, ...] = ()
    expired_options: tuple[ServiceOption, ...] = ()

    @property
    def device_profile(self) -> DeviceProfile:
        """Device profile used for the simulation."""
        return self.traveler.device_profile

    @property
    def eligible(self) -> tuple[ServiceOption, ...]:
        """Alias for eligible_options."""
        return self.eligible_options

    @property
    def rejected(self) -> tuple[RejectedOption, ...]:
        """Alias for rejected_options."""
        return self.rejected_options

    @property
    def unavailable_categories(self) -> tuple[ServiceCategory, ...]:
        """Alias for missing_categories."""
        return self.missing_categories

    @property
    def has_unverified_options(self) -> bool:
        """Return True if any option in the city catalog or result is unverified."""
        return bool(self.unverified_option_ids)

    @property
    def has_stale_options(self) -> bool:
        """Return True if city metadata or any verified option is STALE."""
        return bool(self.stale_option_ids) or self.city_freshness == FreshnessStatus.STALE

    @property
    def has_expired_options(self) -> bool:
        """Return True if city metadata or any verified option is EXPIRED."""
        return bool(self.expired_option_ids) or self.city_freshness == FreshnessStatus.EXPIRED

    @property
    def has_freshness_warnings(self) -> bool:
        """Return True if any verified record is STALE or EXPIRED."""
        return self.has_stale_options or self.has_expired_options

    def scenario_for(self, scenario_type: ScenarioType) -> TripScenario:
        """Return the TripScenario for the given ScenarioType."""
        return self.scenarios[scenario_type]

    def __getitem__(self, scenario_type: ScenarioType) -> TripScenario:
        return self.scenarios[scenario_type]


def _resolve_traveler_and_city(
    *,
    city_or_traveler: str | TravelerProfile | SimulationRequest | None,
    traveler_or_device: TravelerProfile | DeviceProfile | None,
    device_or_none: DeviceProfile | None,
    city_id: str | None,
    traveler: TravelerProfile | None,
    device_profile: DeviceProfile | None,
    trip_duration_days: int | None,
    has_local_id: bool | None,
    target_data_gb: NumericInput | None,
    friction_tolerance: FrictionTolerance | Decimal | None,
    include_day_trips: bool | None,
    dining_preference: DiningPreference | None,
    payment_method_preference: PaymentMethodPreference | None,
    traveler_id: str,
    categories: Sequence[ServiceCategory] | None,
    efficiency_threshold_usd: NumericInput | None,
    max_balanced_friction: NumericInput | None,
    penalty_handoff: NumericInput,
    incompatible_pairs: Collection[tuple[str, str]],
    reference_time: datetime | None,
) -> tuple[
    str,
    TravelerProfile,
    Sequence[ServiceCategory] | None,
    NumericInput | None,
    NumericInput | None,
    NumericInput,
    Collection[tuple[str, str]],
    datetime | None,
]:
    if isinstance(city_or_traveler, SimulationRequest):
        req = city_or_traveler
        effective_traveler = traveler if traveler is not None else req.traveler
        eff_req_threshold = (
            efficiency_threshold_usd
            if efficiency_threshold_usd is not None
            else req.efficiency_threshold_usd
        )
        eff_req_max_friction = (
            max_balanced_friction
            if max_balanced_friction is not None
            else req.max_balanced_friction
        )
        eff_req_penalty = (
            penalty_handoff if penalty_handoff != Decimal(0) else req.penalty_handoff
        )
        eff_req_reference_time = (
            reference_time if reference_time is not None else req.reference_time
        )
        if effective_traveler is not None:
            return _resolve_traveler_and_city(
                city_or_traveler=None,
                traveler_or_device=None,
                device_or_none=None,
                city_id=city_id,
                traveler=effective_traveler,
                device_profile=device_profile,
                trip_duration_days=trip_duration_days,
                has_local_id=has_local_id,
                target_data_gb=target_data_gb,
                friction_tolerance=friction_tolerance,
                include_day_trips=include_day_trips,
                dining_preference=dining_preference,
                payment_method_preference=payment_method_preference,
                traveler_id=traveler_id,
                categories=categories if categories is not None else req.categories,
                efficiency_threshold_usd=eff_req_threshold,
                max_balanced_friction=eff_req_max_friction,
                penalty_handoff=eff_req_penalty,
                incompatible_pairs=incompatible_pairs or req.incompatible_pairs,
                reference_time=eff_req_reference_time,
            )
        return _resolve_traveler_and_city(
            city_or_traveler=None,
            traveler_or_device=None,
            device_or_none=None,
            city_id=city_id if city_id is not None else req.city_id,
            traveler=None,
            device_profile=(
                device_profile if device_profile is not None else req.device_profile
            ),
            trip_duration_days=(
                trip_duration_days
                if trip_duration_days is not None
                else req.trip_duration_days
            ),
            has_local_id=has_local_id if has_local_id is not None else req.has_local_id,
            target_data_gb=(
                target_data_gb if target_data_gb is not None else req.target_data_gb
            ),
            friction_tolerance=(
                friction_tolerance
                if friction_tolerance is not None
                else req.friction_tolerance
            ),
            include_day_trips=(
                include_day_trips
                if include_day_trips is not None
                else req.include_day_trips
            ),
            dining_preference=(
                dining_preference
                if dining_preference is not None
                else req.dining_preference
            ),
            payment_method_preference=(
                payment_method_preference
                if payment_method_preference is not None
                else req.payment_method_preference
            ),
            traveler_id=req.traveler_id or traveler_id,
            categories=categories if categories is not None else req.categories,
            efficiency_threshold_usd=eff_req_threshold,
            max_balanced_friction=eff_req_max_friction,
            penalty_handoff=eff_req_penalty,
            incompatible_pairs=incompatible_pairs or req.incompatible_pairs,
            reference_time=eff_req_reference_time,
        )

    pos_city_id: str | None = None
    pos_traveler: TravelerProfile | None = None
    pos_device: DeviceProfile | None = None

    if isinstance(city_or_traveler, str):
        pos_city_id = city_or_traveler
    elif isinstance(city_or_traveler, TravelerProfile):
        pos_traveler = city_or_traveler

    if isinstance(traveler_or_device, TravelerProfile):
        pos_traveler = traveler_or_device
    elif isinstance(traveler_or_device, DeviceProfile):
        pos_device = traveler_or_device

    if isinstance(device_or_none, DeviceProfile):
        pos_device = device_or_none

    base_traveler = traveler if traveler is not None else pos_traveler
    eff_city_id = city_id if city_id is not None else pos_city_id
    eff_device = device_profile if device_profile is not None else pos_device

    if base_traveler is not None:
        final_city_id = (
            eff_city_id if eff_city_id is not None else base_traveler.destination_city_id
        )
        final_traveler = TravelerProfile(
            id=base_traveler.id,
            destination_city_id=final_city_id,
            trip_duration_days=(
                trip_duration_days
                if trip_duration_days is not None
                else base_traveler.trip_duration_days
            ),
            has_local_id=(
                has_local_id if has_local_id is not None else base_traveler.has_local_id
            ),
            target_data_gb=(
                to_decimal(target_data_gb, "target_data_gb")
                if target_data_gb is not None
                else base_traveler.target_data_gb
            ),
            friction_tolerance=(
                friction_tolerance
                if friction_tolerance is not None
                else base_traveler.friction_tolerance
            ),
            device_profile=(
                eff_device if eff_device is not None else base_traveler.device_profile
            ),
            include_day_trips=(
                include_day_trips
                if include_day_trips is not None
                else base_traveler.include_day_trips
            ),
            dining_preference=(
                dining_preference
                if dining_preference is not None
                else base_traveler.dining_preference
            ),
            payment_method_preference=(
                payment_method_preference
                if payment_method_preference is not None
                else base_traveler.payment_method_preference
            ),
        )
        return (
            final_city_id,
            final_traveler,
            categories,
            efficiency_threshold_usd,
            max_balanced_friction,
            penalty_handoff,
            incompatible_pairs,
            reference_time,
        )

    if eff_city_id is None or not eff_city_id.strip():
        raise ValueError("city_id or traveler must be provided to run simulation")

    final_traveler = TravelerProfile(
        id=traveler_id,
        destination_city_id=eff_city_id,
        trip_duration_days=trip_duration_days if trip_duration_days is not None else 7,
        has_local_id=has_local_id if has_local_id is not None else False,
        target_data_gb=(
            to_decimal(target_data_gb, "target_data_gb")
            if target_data_gb is not None
            else Decimal(0)
        ),
        friction_tolerance=(
            friction_tolerance
            if friction_tolerance is not None
            else FrictionTolerance.MEDIUM
        ),
        device_profile=eff_device if eff_device is not None else DeviceProfile.dual_sim(),
        include_day_trips=include_day_trips if include_day_trips is not None else True,
        dining_preference=(
            dining_preference if dining_preference is not None else DiningPreference.CASUAL
        ),
        payment_method_preference=(
            payment_method_preference
            if payment_method_preference is not None
            else PaymentMethodPreference.INTERNATIONAL_CARD
        ),
    )
    return (
        eff_city_id,
        final_traveler,
        categories,
        efficiency_threshold_usd,
        max_balanced_friction,
        penalty_handoff,
        incompatible_pairs,
        reference_time,
    )


def _collect_unverified_options(
    repository: OptionRepository,
    city_id: str,
    catalog_options: Sequence[ServiceOption],
) -> tuple[tuple[ServiceOption, ...], tuple[str, ...]]:
    unverified_id_set: set[str] = set()

    try:
        repo_unverified = repository.list_unverified_options(city_id)
        for opt in repo_unverified:
            unverified_id_set.add(opt.id)
    except (AttributeError, NotImplementedError):
        pass

    for opt in catalog_options:
        if not opt.is_verified:
            unverified_id_set.add(opt.id)
            continue
        try:
            if not repository.is_verified(opt.id):
                unverified_id_set.add(opt.id)
        except (AttributeError, KeyError, NotImplementedError):
            pass

    ordered_unverified = tuple(opt for opt in catalog_options if opt.id in unverified_id_set)
    ordered_ids = tuple(opt.id for opt in ordered_unverified)
    return ordered_unverified, ordered_ids


def _collect_freshness(
    repository: OptionRepository,
    city: City | None,
    city_unverified: bool,
    catalog_options: Sequence[ServiceOption],
    unverified_option_ids: Collection[str],
    reference_time: datetime | None,
) -> tuple[
    FreshnessStatus | None,
    Mapping[str, FreshnessStatus],
    tuple[ServiceOption, ...],
    tuple[str, ...],
    tuple[ServiceOption, ...],
    tuple[str, ...],
]:
    if reference_time is None:
        return None, MappingProxyType({}), (), (), (), ()

    city_freshness: FreshnessStatus | None = None
    if city is not None and not city_unverified and isinstance(city.last_verified_at, str):
        city_freshness = freshness_status(city.last_verified_at, reference_time)

    unverified_set = set(unverified_option_ids)
    freshness_map: dict[str, FreshnessStatus] = {}
    stale_opts: list[ServiceOption] = []
    expired_opts: list[ServiceOption] = []

    for opt in catalog_options:
        if opt.id in unverified_set or not opt.is_verified:
            continue
        status: FreshnessStatus | None
        try:
            status = repository.get_freshness_status(opt.id, reference_time=reference_time)
        except (AttributeError, KeyError, NotImplementedError):
            status = opt.freshness_status(reference_time)
        if status is None:
            continue
        freshness_map[opt.id] = status
        if status == FreshnessStatus.STALE:
            stale_opts.append(opt)
        elif status == FreshnessStatus.EXPIRED:
            expired_opts.append(opt)

    return (
        city_freshness,
        MappingProxyType(freshness_map),
        tuple(stale_opts),
        tuple(opt.id for opt in stale_opts),
        tuple(expired_opts),
        tuple(opt.id for opt in expired_opts),
    )


def simulate(
    repository: OptionRepository,
    city_or_traveler: str | TravelerProfile | SimulationRequest | None = None,
    traveler_or_device: TravelerProfile | DeviceProfile | None = None,
    device_or_none: DeviceProfile | None = None,
    *,
    city_id: str | None = None,
    traveler: TravelerProfile | None = None,
    device_profile: DeviceProfile | None = None,
    trip_duration_days: int | None = None,
    has_local_id: bool | None = None,
    target_data_gb: NumericInput | None = None,
    friction_tolerance: FrictionTolerance | Decimal | None = None,
    include_day_trips: bool | None = None,
    dining_preference: DiningPreference | None = None,
    payment_method_preference: PaymentMethodPreference | None = None,
    traveler_id: str = "traveler-default",
    categories: Sequence[ServiceCategory] | None = None,
    efficiency_threshold_usd: NumericInput | None = None,
    max_balanced_friction: NumericInput | None = None,
    penalty_handoff: NumericInput = Decimal(0),
    incompatible_pairs: Collection[tuple[str, str]] = (),
    reference_time: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
) -> SimulationResult:
    """Execute the deterministic travel cost-vs-friction simulation use case."""
    (
        resolved_city_id,
        resolved_traveler,
        resolved_categories,
        eff_threshold,
        eff_max_friction,
        eff_penalty,
        eff_incompat_pairs,
        resolved_reference_time,
    ) = _resolve_traveler_and_city(
        city_or_traveler=city_or_traveler,
        traveler_or_device=traveler_or_device,
        device_or_none=device_or_none,
        city_id=city_id,
        traveler=traveler,
        device_profile=device_profile,
        trip_duration_days=trip_duration_days,
        has_local_id=has_local_id,
        target_data_gb=target_data_gb,
        friction_tolerance=friction_tolerance,
        include_day_trips=include_day_trips,
        dining_preference=dining_preference,
        payment_method_preference=payment_method_preference,
        traveler_id=traveler_id,
        categories=categories,
        efficiency_threshold_usd=efficiency_threshold_usd,
        max_balanced_friction=max_balanced_friction,
        penalty_handoff=penalty_handoff,
        incompatible_pairs=incompatible_pairs,
        reference_time=reference_time,
    )

    eff_reference_time = (
        resolved_reference_time
        if resolved_reference_time is not None
        else (clock() if clock is not None else None)
    )

    city = repository.get_city(resolved_city_id)
    city_unverified = city is not None and not city.is_verified

    catalog_options = tuple(repository.list_options(resolved_city_id))
    unverified_options, unverified_option_ids = _collect_unverified_options(
        repository,
        resolved_city_id,
        catalog_options,
    )
    (
        city_freshness,
        option_freshness,
        stale_options,
        stale_option_ids,
        expired_options,
        expired_option_ids,
    ) = _collect_freshness(
        repository,
        city,
        city_unverified,
        catalog_options,
        unverified_option_ids,
        eff_reference_time,
    )

    hard_filter_result: HardFilterResult = apply_hard_filters(
        catalog_options,
        resolved_traveler,
        incompatible_pairs=eff_incompat_pairs,
    )

    scenario_build = build_scenarios(
        hard_filter_result,
        resolved_traveler,
        categories=resolved_categories,
        efficiency_threshold_usd=eff_threshold,
        max_balanced_friction=eff_max_friction,
        penalty_handoff=eff_penalty,
        incompatible_pairs=eff_incompat_pairs,
        unverified_option_ids=unverified_option_ids,
    )

    per_category_choices: dict[
        ServiceCategory, Mapping[ScenarioType, CategoryChoice | None]
    ] = {}
    for cat in scenario_build.categories:
        bundle = scenario_build.category_scenarios[cat]
        per_category_choices[cat] = MappingProxyType(bundle.as_dict())

    totals_map: dict[ScenarioType, ScenarioTotals] = {}
    for scen_type, scen in scenario_build.scenarios.items():
        totals_map[scen_type] = ScenarioTotals(
            scenario_type=scen_type,
            total_cost_usd=scen.total_cost_usd,
            total_cost_local=scen.total_cost_local,
            total_cost_clp=scen.total_cost_clp,
            daily_cost_usd=scen.daily_cost_usd,
            daily_cost_local=scen.daily_cost_local,
            daily_cost_clp=scen.daily_cost_clp,
            friction_score=scen.friction_score,
            total_friction_score=scen.total_friction_score,
            total_setup_time_minutes=scen.total_setup_time_minutes,
            extra_time_minutes=scen.extra_time_minutes,
        )

    is_unverified = (
        city_unverified
        or bool(unverified_option_ids)
        or scenario_build.unverified
    )

    return SimulationResult(
        city_id=resolved_city_id,
        city=city,
        traveler=resolved_traveler,
        categories=scenario_build.categories,
        category_scenarios=scenario_build.category_scenarios,
        per_category_choices=MappingProxyType(per_category_choices),
        scenarios=scenario_build.scenarios,
        zero_friction=scenario_build.zero_friction,
        balanced=scenario_build.balanced,
        local_optimized=scenario_build.local_optimized,
        totals=MappingProxyType(totals_map),
        savings=scenario_build.savings,
        eligible_options=hard_filter_result.eligible,
        rejected_options=hard_filter_result.rejected,
        missing_categories=scenario_build.missing_categories,
        unverified=is_unverified,
        city_unverified=city_unverified,
        unverified_option_ids=unverified_option_ids,
        unverified_options=unverified_options,
        city_freshness=city_freshness,
        option_freshness=option_freshness,
        stale_option_ids=stale_option_ids,
        expired_option_ids=expired_option_ids,
        stale_options=stale_options,
        expired_options=expired_options,
    )


class SimulateTripUseCase:
    """Application use case wrapping `simulate` with an injected OptionRepository."""

    def __init__(
        self,
        repository: OptionRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock

    @property
    def repository(self) -> OptionRepository:
        """Return the underlying OptionRepository port."""
        return self._repository

    def execute(
        self,
        city_or_traveler: str | TravelerProfile | SimulationRequest | None = None,
        traveler_or_device: TravelerProfile | DeviceProfile | None = None,
        device_or_none: DeviceProfile | None = None,
        *,
        city_id: str | None = None,
        traveler: TravelerProfile | None = None,
        device_profile: DeviceProfile | None = None,
        trip_duration_days: int | None = None,
        has_local_id: bool | None = None,
        target_data_gb: NumericInput | None = None,
        friction_tolerance: FrictionTolerance | Decimal | None = None,
        include_day_trips: bool | None = None,
        dining_preference: DiningPreference | None = None,
        payment_method_preference: PaymentMethodPreference | None = None,
        traveler_id: str = "traveler-default",
        categories: Sequence[ServiceCategory] | None = None,
        efficiency_threshold_usd: NumericInput | None = None,
        max_balanced_friction: NumericInput | None = None,
        penalty_handoff: NumericInput = Decimal(0),
        incompatible_pairs: Collection[tuple[str, str]] = (),
        reference_time: datetime | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> SimulationResult:
        """Run the simulation against the configured OptionRepository."""
        return simulate(
            self._repository,
            city_or_traveler,
            traveler_or_device,
            device_or_none,
            city_id=city_id,
            traveler=traveler,
            device_profile=device_profile,
            trip_duration_days=trip_duration_days,
            has_local_id=has_local_id,
            target_data_gb=target_data_gb,
            friction_tolerance=friction_tolerance,
            include_day_trips=include_day_trips,
            dining_preference=dining_preference,
            payment_method_preference=payment_method_preference,
            traveler_id=traveler_id,
            categories=categories,
            efficiency_threshold_usd=efficiency_threshold_usd,
            max_balanced_friction=max_balanced_friction,
            penalty_handoff=penalty_handoff,
            incompatible_pairs=incompatible_pairs,
            reference_time=reference_time,
            clock=clock if clock is not None else self._clock,
        )

    run = execute
    __call__ = execute


SimulationRequestDto = SimulationRequest
SimulationResultDto = SimulationResult
RunSimulationUseCase = SimulateTripUseCase
run_simulation = simulate

__all__ = [
    "RunSimulationUseCase",
    "ScenarioTotals",
    "SimulateTripUseCase",
    "SimulationRequest",
    "SimulationRequestDto",
    "SimulationResult",
    "SimulationResultDto",
    "run_simulation",
    "simulate",
]
