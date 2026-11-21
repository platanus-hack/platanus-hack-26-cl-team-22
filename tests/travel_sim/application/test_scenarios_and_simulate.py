"""Unit tests for the deterministic scenario engine and simulate use case."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from travel_sim.application.filters import RejectionReason
from travel_sim.application.ports import OptionRepository
from travel_sim.application.scenarios import (
    build_category_scenarios,
    build_scenarios,
)
from travel_sim.application.simulate import (
    RunSimulationUseCase,
    SimulationRequest,
    simulate,
)
from travel_sim.domain import (
    City,
    DeviceProfile,
    DiningPreference,
    FreshnessStatus,
    FrictionTolerance,
    PaymentMethodPreference,
    PricingModel,
    ScenarioType,
    ServiceCategory,
    ServiceOption,
    SimType,
    TravelerProfile,
    freshness_status,
)
from travel_sim.infrastructure.json_repository import JsonOptionRepository

REPO_ROOT = Path(__file__).resolve().parents[3]
SANTIAGO_SEED_PATH = REPO_ROOT / "data" / "cities" / "santiago.json"
# Seed options that carry a real source and verification date.
SOURCED_SEED_IDS = {
    "scl-conn-wom-plan-zero-esim",
    "scl-transfer-centropuerto-bus",
    "scl-dining-menu-del-dia",
    "scl-dining-menu-ejecutivo",
}


class InMemoryOptionRepository(OptionRepository):
    """Lightweight in-memory OptionRepository test double."""

    def __init__(
        self,
        city: City,
        options: Sequence[ServiceOption],
        *,
        unverified_ids: frozenset[str] = frozenset(),
    ) -> None:
        self._city = city
        self._options = tuple(options)
        self._by_id = {opt.id: opt for opt in self._options}
        self._unverified_ids = unverified_ids

    def list_cities(self) -> Sequence[City]:
        return (self._city,)

    def get_city(self, city_id: str) -> City | None:
        return self._city if self._city.id == city_id else None

    def list_options(
        self,
        city_id: str,
        category: ServiceCategory | None = None,
    ) -> Sequence[ServiceOption]:
        if city_id != self._city.id:
            return ()
        if category is None:
            return self._options
        return tuple(opt for opt in self._options if opt.category == category)

    def list_options_by_city_and_category(
        self,
        city_id: str,
        category: ServiceCategory,
    ) -> Sequence[ServiceOption]:
        return self.list_options(city_id, category=category)

    def get_option(self, option_id: str) -> ServiceOption | None:
        return self._by_id.get(option_id)

    def is_verified(self, option_id: str) -> bool:
        if option_id not in self._by_id:
            raise KeyError(option_id)
        return option_id not in self._unverified_ids

    def get_freshness_status(
        self,
        option_id: str,
        reference_time: datetime | None = None,
    ) -> FreshnessStatus | None:
        if not self.is_verified(option_id):
            return None
        opt = self._by_id[option_id]
        if reference_time is None:
            return FreshnessStatus.FRESH
        return freshness_status(opt.last_verified_at, reference_time)

    def list_unverified_options(
        self,
        city_id: str | None = None,
    ) -> Sequence[ServiceOption]:
        if city_id is not None and city_id != self._city.id:
            return ()
        return tuple(opt for opt in self._options if opt.id in self._unverified_ids)


def _make_traveler(
    *,
    city_id: str = "scl",
    trip_duration_days: int = 7,
    has_local_id: bool = False,
    target_data_gb: Decimal = Decimal("5.0"),
    device_profile: DeviceProfile | None = None,
    include_day_trips: bool = True,
    payment_method_preference: PaymentMethodPreference = (
        PaymentMethodPreference.INTERNATIONAL_CARD
    ),
) -> TravelerProfile:
    return TravelerProfile(
        id="traveler-test-1",
        destination_city_id=city_id,
        trip_duration_days=trip_duration_days,
        has_local_id=has_local_id,
        target_data_gb=target_data_gb,
        friction_tolerance=FrictionTolerance.MEDIUM,
        device_profile=device_profile or DeviceProfile.dual_sim(),
        include_day_trips=include_day_trips,
        dining_preference=DiningPreference.CASUAL,
        payment_method_preference=payment_method_preference,
    )


def _make_option(
    *,
    option_id: str,
    category: ServiceCategory,
    cost_local: Decimal | str | int,
    cost_usd: Decimal | str | int,
    setup_time_minutes: int = 10,
    paperwork_level: int = 0,
    language_barrier_level: int = 0,
    physical_presence_required: bool = False,
    uncertainty_risk_level: int = 0,
    requires_local_id: bool = False,
    sim_type: SimType = SimType.NOT_APPLICABLE,
    pricing_model: PricingModel = PricingModel.PER_TRIP,
    validity_days: int = 1,
    data_quota_gb: Decimal | str | int | None = None,
    requires_international_card: bool = False,
    allows_top_up: bool = True,
) -> ServiceOption:
    return ServiceOption(
        id=option_id,
        city_id="scl",
        category=category,
        provider="TestProvider",
        name=f"Option {option_id}",
        cost_local_currency=Decimal(str(cost_local)),
        cost_usd_reference=Decimal(str(cost_usd)),
        pricing_model=pricing_model,
        validity_days=validity_days,
        data_quota_gb=Decimal(str(data_quota_gb)) if data_quota_gb is not None else None,
        setup_time_minutes=setup_time_minutes,
        paperwork_level=paperwork_level,
        language_barrier_level=language_barrier_level,
        physical_presence_required=physical_presence_required,
        uncertainty_risk_level=uncertainty_risk_level,
        requires_local_id=requires_local_id,
        sim_type=sim_type,
        is_tourist_friendly=not requires_local_id,
        last_verified_at="2026-11-20T00:00:00Z",
        verification_source_url="https://example.com",
        requires_international_card=requires_international_card,
        allows_top_up=allows_top_up,
    )


def _build_hand_dataset() -> tuple[City, tuple[ServiceOption, ...]]:
    city = City(
        id="scl",
        name="Santiago",
        country_code="CL",
        local_currency="CLP",
        default_usd_exchange_rate=Decimal(950),
        last_verified_at="2026-11-20T00:00:00Z",
    )
    options = (
        # CONNECTIVITY:
        # 1) Global eSIM: low friction (setup=6 -> 3.0), high cost ($30.00 / 28500 CLP)
        _make_option(
            option_id="conn-esim-global",
            category=ServiceCategory.CONNECTIVITY,
            cost_local=28500,
            cost_usd="30.00",
            setup_time_minutes=6,
            paperwork_level=0,
            language_barrier_level=0,
            physical_presence_required=False,
            uncertainty_risk_level=0,
            sim_type=SimType.ESIM,
            pricing_model=PricingModel.ONE_TIME_PACKAGE,
            validity_days=30,
            data_quota_gb=20,
        ),
        # 2) Local eSIM: moderate friction (setup=20 -> 10, lang=1 -> 7.5 => 17.5),
        #    low cost ($10.50 / 10000 CLP). Savings = $19.50 over 14.5 friction => 1.34 USD/pt
        _make_option(
            option_id="conn-esim-local",
            category=ServiceCategory.CONNECTIVITY,
            cost_local=10000,
            cost_usd="10.50",
            setup_time_minutes=20,
            paperwork_level=0,
            language_barrier_level=1,
            physical_presence_required=False,
            uncertainty_risk_level=0,
            sim_type=SimType.ESIM,
            pricing_model=PricingModel.ONE_TIME_PACKAGE,
            validity_days=30,
            data_quota_gb=50,
        ),
        # 3) Local Physical SIM: high friction (setup=40 -> 20, physical -> 20, lang=1 -> 7.5,
        #    risk=1 -> 5 => 52.5 > 50 max balanced friction), cheapest ($5.00 / 4750 CLP)
        _make_option(
            option_id="conn-phys-cheap",
            category=ServiceCategory.CONNECTIVITY,
            cost_local=4750,
            cost_usd="5.00",
            setup_time_minutes=40,
            paperwork_level=0,
            language_barrier_level=1,
            physical_presence_required=True,
            uncertainty_risk_level=1,
            sim_type=SimType.PHYSICAL_SIM,
            pricing_model=PricingModel.ONE_TIME_PACKAGE,
            validity_days=30,
            data_quota_gb=50,
        ),
        # 4) RUT-only postpaid plan: ultra cheap ($2.00 / 1900 CLP), requires local ID
        _make_option(
            option_id="conn-rut-only",
            category=ServiceCategory.CONNECTIVITY,
            cost_local=1900,
            cost_usd="2.00",
            setup_time_minutes=10,
            requires_local_id=True,
            sim_type=SimType.ESIM,
            pricing_model=PricingModel.ONE_TIME_PACKAGE,
            validity_days=30,
            data_quota_gb=100,
        ),
        # AIRPORT_TRANSFER:
        # 1) Private transfer: zero friction (setup=10 -> 5.0), cost $25.00 / 23750 CLP
        _make_option(
            option_id="transfer-private",
            category=ServiceCategory.AIRPORT_TRANSFER,
            cost_local=23750,
            cost_usd="25.00",
            setup_time_minutes=10,
        ),
        # 2) Public bus: friction (setup=30 -> 15 + physical 20 + lang 7.5 = 42.5),
        #    cost $2.00 / 1900 CLP (saves $23 over 37.5 pts = 0.613 < 0.75, so Balanced keeps private)
        _make_option(
            option_id="transfer-bus",
            category=ServiceCategory.AIRPORT_TRANSFER,
            cost_local=1900,
            cost_usd="2.00",
            setup_time_minutes=30,
            language_barrier_level=1,
            physical_presence_required=True,
        ),
    )
    return city, options


def test_esim_only_device_never_gets_physical_sim_in_any_scenario() -> None:
    city, options = _build_hand_dataset()
    repo = InMemoryOptionRepository(city, options)
    traveler = _make_traveler(
        device_profile=DeviceProfile.esim_only(),
        has_local_id=True,
    )

    result = simulate(repo, traveler=traveler)

    for scenario_type in ScenarioType:
        scenario = result.scenarios[scenario_type]
        for choice in scenario.choices:
            assert choice.option.sim_type != SimType.PHYSICAL_SIM

    rejected_by_id = {item.option.id: item.reasons for item in result.rejected_options}
    assert "conn-phys-cheap" in rejected_by_id
    assert RejectionReason.UNSUPPORTED_PHYSICAL_SIM in rejected_by_id["conn-phys-cheap"]


def test_traveler_without_rut_never_gets_rut_only_options() -> None:
    city, options = _build_hand_dataset()
    repo = InMemoryOptionRepository(city, options)
    traveler = _make_traveler(
        device_profile=DeviceProfile.dual_sim(),
        has_local_id=False,
    )

    result = simulate(repo, traveler=traveler)

    for scenario_type in ScenarioType:
        scenario = result.scenarios[scenario_type]
        for choice in scenario.choices:
            assert not choice.option.requires_local_id
            assert choice.option.id != "conn-rut-only"

    rejected_by_id = {item.option.id: item.reasons for item in result.rejected_options}
    assert "conn-rut-only" in rejected_by_id
    assert RejectionReason.REQUIRES_LOCAL_ID in rejected_by_id["conn-rut-only"]


def test_zero_friction_lowest_friction_and_local_optimized_highest_savings() -> None:
    city, options = _build_hand_dataset()
    repo = InMemoryOptionRepository(city, options)
    traveler = _make_traveler(
        device_profile=DeviceProfile.dual_sim(),
        has_local_id=False,
    )

    result = simulate(repo, traveler=traveler)

    zero = result.zero_friction
    balanced = result.balanced
    local = result.local_optimized

    # Selected option IDs across the 3 scenarios:
    # ZERO_FRICTION: conn-esim-global ($30, f=3) + transfer-private ($25, f=5)
    # BALANCED: conn-esim-local ($10.50, f=17.5) + transfer-private ($25, f=5)
    # LOCAL_OPTIMIZED: conn-phys-cheap ($5, f=52.5) + transfer-bus ($2, f=42.5)
    assert [c.option.id for c in zero.choices] == ["conn-esim-global", "transfer-private"]
    assert [c.option.id for c in balanced.choices] == ["conn-esim-local", "transfer-private"]
    assert [c.option.id for c in local.choices] == ["conn-phys-cheap", "transfer-bus"]

    assert zero.friction_score < balanced.friction_score < local.friction_score
    assert zero.total_friction_score < balanced.total_friction_score < local.total_friction_score
    assert zero.savings_usd < balanced.savings_usd < local.savings_usd
    assert zero.savings_clp < balanced.savings_clp < local.savings_clp


def test_savings_arithmetic_is_exact() -> None:
    city, options = _build_hand_dataset()
    repo = InMemoryOptionRepository(city, options)
    traveler = _make_traveler(
        device_profile=DeviceProfile.dual_sim(),
        has_local_id=False,
    )

    result = simulate(repo, traveler=traveler)

    zero = result.zero_friction
    balanced = result.balanced
    local = result.local_optimized

    # Baseline (Zero Friction): $30.00 + $25.00 = $55.00 USD; 28500 + 23750 = 52250 CLP
    assert zero.total_cost_usd == Decimal("55.00")
    assert zero.total_cost_local == Decimal(52250)
    assert zero.total_cost_clp == Decimal(52250)
    assert zero.savings.savings_usd == Decimal("0.00")
    assert zero.savings.savings_clp == Decimal(0)
    assert zero.savings.savings_percentage == Decimal(0)
    assert zero.extra_time_minutes == 0

    # Balanced: $10.50 + $25.00 = $35.50 USD; 10000 + 23750 = 33750 CLP
    # Savings vs Zero Friction: $55.00 - $35.50 = $19.50 USD; 52250 - 33750 = 18500 CLP
    assert balanced.total_cost_usd == Decimal("35.50")
    assert balanced.total_cost_clp == Decimal(33750)
    assert balanced.savings.savings_usd == Decimal("19.50")
    assert balanced.savings.savings_local == Decimal(18500)
    assert balanced.savings.savings_clp == Decimal(18500)
    assert balanced.savings.savings_percentage == (Decimal("19.50") / Decimal("55.00")) * Decimal(
        100
    )
    assert balanced.extra_time_minutes == 14

    # Local Optimized: $5.00 + $2.00 = $7.00 USD; 4750 + 1900 = 6650 CLP
    # Savings vs Zero Friction: $55.00 - $7.00 = $48.00 USD; 52250 - 6650 = 45600 CLP
    assert local.total_cost_usd == Decimal("7.00")
    assert local.total_cost_clp == Decimal(6650)
    assert local.savings.savings_usd == Decimal("48.00")
    assert local.savings.savings_local == Decimal(45600)
    assert local.savings.savings_clp == Decimal(45600)
    assert local.savings.savings_percentage == (Decimal("48.00") / Decimal("55.00")) * Decimal(100)
    assert local.extra_time_minutes == (40 - 6) + (30 - 10)


def test_same_inputs_give_identical_output_and_deterministic_tie_breaking() -> None:
    city = City(
        id="scl",
        name="Santiago",
        country_code="CL",
        local_currency="CLP",
        default_usd_exchange_rate=Decimal(950),
        last_verified_at="2026-11-20T00:00:00Z",
    )
    tied_a = _make_option(
        option_id="opt-alpha",
        category=ServiceCategory.URBAN_TRANSIT,
        cost_local=2000,
        cost_usd="2.00",
        setup_time_minutes=10,
    )
    tied_b = _make_option(
        option_id="opt-beta",
        category=ServiceCategory.URBAN_TRANSIT,
        cost_local=2000,
        cost_usd="2.00",
        setup_time_minutes=10,
    )
    traveler = _make_traveler()

    repo_forward = InMemoryOptionRepository(city, (tied_a, tied_b))
    repo_reverse = InMemoryOptionRepository(city, (tied_b, tied_a))

    run_1 = simulate(repo_forward, traveler=traveler)
    run_2 = simulate(repo_forward, traveler=traveler)
    run_reverse = simulate(repo_reverse, traveler=traveler)

    assert run_1 == run_2
    assert run_1.zero_friction.choices[0].option.id == "opt-alpha"
    assert run_1.balanced.choices[0].option.id == "opt-alpha"
    assert run_1.local_optimized.choices[0].option.id == "opt-alpha"
    assert run_reverse.zero_friction.choices[0].option.id == "opt-alpha"
    assert run_reverse.balanced.choices[0].option.id == "opt-alpha"
    assert run_reverse.local_optimized.choices[0].option.id == "opt-alpha"


def test_category_with_no_compatible_option_is_reported_without_crashing() -> None:
    city = City(
        id="scl",
        name="Santiago",
        country_code="CL",
        local_currency="CLP",
        default_usd_exchange_rate=Decimal(950),
        last_verified_at="2026-11-20T00:00:00Z",
    )
    # Only a physical SIM exists in CONNECTIVITY, while AIRPORT_TRANSFER has a valid option
    only_phys_sim = _make_option(
        option_id="conn-phys-only",
        category=ServiceCategory.CONNECTIVITY,
        cost_local=10000,
        cost_usd="10.50",
        sim_type=SimType.PHYSICAL_SIM,
        pricing_model=PricingModel.ONE_TIME_PACKAGE,
        validity_days=30,
        data_quota_gb=50,
    )
    valid_transfer = _make_option(
        option_id="transfer-valid",
        category=ServiceCategory.AIRPORT_TRANSFER,
        cost_local=10000,
        cost_usd="10.50",
    )
    repo = InMemoryOptionRepository(city, (only_phys_sim, valid_transfer))
    esim_traveler = _make_traveler(device_profile=DeviceProfile.esim_only())

    result = simulate(repo, traveler=esim_traveler)

    assert ServiceCategory.CONNECTIVITY in result.missing_categories
    assert ServiceCategory.CONNECTIVITY in result.unavailable_categories
    conn_bundle = result.category_scenarios[ServiceCategory.CONNECTIVITY]
    assert conn_bundle.has_compatible_option is False
    assert conn_bundle.zero_friction is None
    assert conn_bundle.balanced is None
    assert conn_bundle.local_optimized is None
    assert conn_bundle.status_message is not None

    # Direct single-category and empty-catalog calls also report without crashing
    empty_bundle = build_category_scenarios(
        ServiceCategory.DINING,
        (),
        esim_traveler,
    )
    assert empty_bundle.has_compatible_option is False
    assert empty_bundle.zero_friction is None

    all_missing = build_scenarios(
        (only_phys_sim,),
        esim_traveler,
    )
    # Every required category without a compatible option is reported, not only CONNECTIVITY.
    assert ServiceCategory.CONNECTIVITY in all_missing.missing_categories
    assert len(all_missing.missing_categories) >= 1
    assert all_missing.zero_friction.total_cost_usd == Decimal(0)
    assert all_missing.zero_friction.friction_score == Decimal(0)


def test_end_to_end_santiago_seed_with_unverified_flag_propagated() -> None:
    repo = JsonOptionRepository(SANTIAGO_SEED_PATH)
    use_case = RunSimulationUseCase(repo)

    request = SimulationRequest(
        city_id="scl",
        device_profile=DeviceProfile.esim_only(),
        trip_duration_days=7,
        has_local_id=False,
        target_data_gb=Decimal("10.0"),
    )
    result = use_case.execute(request)

    assert result.city_id == "scl"
    assert result.city is not None
    assert result.city.name == "Santiago"

    # Unverified flag must propagate from Santiago seed into result, scenarios, and choices
    assert result.unverified is True
    assert result.city_unverified is True
    assert result.has_unverified_options is True
    assert len(result.unverified_options) == 9
    assert len(result.unverified_option_ids) == 9

    for scenario_type in ScenarioType:
        scenario = result.scenarios[scenario_type]
        assert scenario.unverified is True
        assert scenario.has_unverified_options is True
        assert len(scenario.choices) == 5
        for choice in scenario.choices:
            sourced = choice.option.id in SOURCED_SEED_IDS
            assert choice.unverified is (not sourced)
            assert choice.is_verified is sourced
            assert choice.option.sim_type != SimType.PHYSICAL_SIM

    # Physical SIMs in Santiago seed (WOM chip fisico & Entel chip fisico) are rejected
    rejected_ids = {r.option.id for r in result.rejected_options}
    assert rejected_ids == {"scl-conn-wom-chip-fisico", "scl-conn-entel-chip-fisico"}

    # Verify ordering of friction and savings on the Santiago seed
    assert (
        result.zero_friction.friction_score
        < result.balanced.friction_score
        < result.local_optimized.friction_score
    )
    assert (
        result.zero_friction.savings_usd
        < result.balanced.savings_usd
        < result.local_optimized.savings_usd
    )
    assert (
        result.zero_friction.savings_clp
        < result.balanced.savings_clp
        < result.local_optimized.savings_clp
    )
