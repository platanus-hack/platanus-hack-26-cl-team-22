"""Domain entities for the deterministic travel cost-vs-friction engine."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from travel_sim.domain import friction as _friction
from travel_sim.domain import normalization as _normalization
from travel_sim.domain.enums import (
    DiningPreference,
    FreshnessStatus,
    FrictionTolerance,
    PaymentMethodPreference,
    PricingModel,
    ServiceCategory,
    SimType,
)
from travel_sim.domain.value_objects import (
    DeviceProfile,
    FrictionScore,
    NumericInput,
    to_decimal,
)


def _require_non_empty_str(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_int_in_range(
    value: int,
    field_name: str,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an int")
    if value < minimum or (maximum is not None and value > maximum):
        bound = f"[{minimum}, {maximum}]" if maximum is not None else f">= {minimum}"
        raise ValueError(f"{field_name} must be {bound}, got {value}")
    return value


@dataclass(frozen=True, slots=True)
class City:
    """Destination city or region metadata (city-agnostic schema)."""

    id: str
    name: str
    country_code: str
    local_currency: str
    default_usd_exchange_rate: Decimal
    last_verified_at: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.id, "id")
        _require_non_empty_str(self.name, "name")
        _require_non_empty_str(self.last_verified_at, "last_verified_at")

        country = self.country_code.strip().upper()
        if len(country) != 2 or not country.isalpha():
            raise ValueError(
                f"country_code must be a 2-letter ISO 3166-1 code, got {self.country_code!r}"
            )
        currency = self.local_currency.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError(
                f"local_currency must be a 3-letter ISO 4217 code, got {self.local_currency!r}"
            )
        rate = to_decimal(self.default_usd_exchange_rate, "default_usd_exchange_rate")
        if rate <= 0:
            raise ValueError(f"default_usd_exchange_rate must be > 0, got {rate}")

        object.__setattr__(self, "country_code", country)
        object.__setattr__(self, "local_currency", currency)
        object.__setattr__(self, "default_usd_exchange_rate", rate)

    @property
    def is_verified(self) -> bool:
        """Return True when last_verified_at is a non-empty timestamp string."""
        return isinstance(self.last_verified_at, str) and bool(self.last_verified_at.strip())


@dataclass(frozen=True, slots=True)
class TravelerProfile:
    """Simulation input profile describing the traveler and trip constraints."""

    id: str
    destination_city_id: str
    trip_duration_days: int
    has_local_id: bool
    target_data_gb: Decimal
    friction_tolerance: FrictionTolerance | Decimal
    device_profile: DeviceProfile
    include_day_trips: bool
    dining_preference: DiningPreference
    payment_method_preference: PaymentMethodPreference

    def __post_init__(self) -> None:
        _require_non_empty_str(self.id, "id")
        _require_non_empty_str(self.destination_city_id, "destination_city_id")
        _require_int_in_range(self.trip_duration_days, "trip_duration_days", minimum=1)

        if not isinstance(self.has_local_id, bool):
            raise TypeError("has_local_id must be a bool")
        if not isinstance(self.include_day_trips, bool):
            raise TypeError("include_day_trips must be a bool")
        if not isinstance(self.device_profile, DeviceProfile):
            raise TypeError("device_profile must be a DeviceProfile")
        if not isinstance(self.dining_preference, DiningPreference):
            raise TypeError("dining_preference must be a DiningPreference")
        if not isinstance(self.payment_method_preference, PaymentMethodPreference):
            raise TypeError("payment_method_preference must be a PaymentMethodPreference")

        target_gb = to_decimal(self.target_data_gb, "target_data_gb")
        if target_gb < 0:
            raise ValueError(f"target_data_gb must be >= 0, got {target_gb}")
        object.__setattr__(self, "target_data_gb", target_gb)

        if not isinstance(self.friction_tolerance, FrictionTolerance):
            tol = to_decimal(self.friction_tolerance, "friction_tolerance")
            if not (Decimal(0) <= tol <= Decimal(1)):
                raise ValueError(f"numeric friction_tolerance must be in [0, 1], got {tol}")
            object.__setattr__(self, "friction_tolerance", tol)


@dataclass(frozen=True, slots=True)
class ServiceOption:
    """Catalog option separating monetary cost from operational friction."""

    id: str
    city_id: str
    category: ServiceCategory
    provider: str
    name: str
    cost_local_currency: Decimal
    cost_usd_reference: Decimal
    pricing_model: PricingModel
    validity_days: int
    data_quota_gb: Decimal | None
    setup_time_minutes: int
    paperwork_level: int
    language_barrier_level: int
    physical_presence_required: bool
    uncertainty_risk_level: int
    requires_local_id: bool
    sim_type: SimType
    is_tourist_friendly: bool
    last_verified_at: str
    verification_source_url: str
    notes: str = ""
    requires_international_card: bool = False
    allows_top_up: bool = True
    incompatible_option_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        _require_non_empty_str(self.id, "id")
        _require_non_empty_str(self.city_id, "city_id")
        _require_non_empty_str(self.provider, "provider")
        _require_non_empty_str(self.name, "name")
        _require_non_empty_str(self.last_verified_at, "last_verified_at")

        if not isinstance(self.category, ServiceCategory):
            raise TypeError("category must be a ServiceCategory")
        if not isinstance(self.pricing_model, PricingModel):
            raise TypeError("pricing_model must be a PricingModel")
        if not isinstance(self.sim_type, SimType):
            raise TypeError("sim_type must be a SimType")

        for bool_field in (
            "physical_presence_required",
            "requires_local_id",
            "is_tourist_friendly",
            "requires_international_card",
            "allows_top_up",
        ):
            if not isinstance(getattr(self, bool_field), bool):
                raise TypeError(f"{bool_field} must be a bool")

        cost_local = to_decimal(self.cost_local_currency, "cost_local_currency")
        cost_usd = to_decimal(self.cost_usd_reference, "cost_usd_reference")
        if cost_local < 0:
            raise ValueError(f"cost_local_currency must be >= 0, got {cost_local}")
        if cost_usd < 0:
            raise ValueError(f"cost_usd_reference must be >= 0, got {cost_usd}")
        object.__setattr__(self, "cost_local_currency", cost_local)
        object.__setattr__(self, "cost_usd_reference", cost_usd)

        _require_int_in_range(self.validity_days, "validity_days", minimum=1)
        _require_int_in_range(self.setup_time_minutes, "setup_time_minutes", minimum=0)
        _require_int_in_range(
            self.paperwork_level,
            "paperwork_level",
            minimum=0,
            maximum=_friction.MAX_PAPERWORK_LEVEL,
        )
        _require_int_in_range(
            self.language_barrier_level,
            "language_barrier_level",
            minimum=0,
            maximum=_friction.MAX_LANGUAGE_BARRIER_LEVEL,
        )
        _require_int_in_range(
            self.uncertainty_risk_level,
            "uncertainty_risk_level",
            minimum=0,
            maximum=_friction.MAX_UNCERTAINTY_RISK_LEVEL,
        )

        if self.data_quota_gb is not None:
            quota = to_decimal(self.data_quota_gb, "data_quota_gb")
            if quota < 0:
                raise ValueError(f"data_quota_gb must be >= 0, got {quota}")
            object.__setattr__(self, "data_quota_gb", quota)

        if isinstance(self.incompatible_option_ids, str):
            raise TypeError("incompatible_option_ids must be an iterable of option IDs, not str")
        if isinstance(self.incompatible_option_ids, Iterable):
            incompat = frozenset(self.incompatible_option_ids)
        else:
            raise TypeError("incompatible_option_ids must be an iterable of option IDs")
        object.__setattr__(self, "incompatible_option_ids", incompat)

    def packages_needed(self, trip_duration_days: int) -> int:
        """Number of packages/units required for the given trip duration."""
        return _normalization.packages_needed(self, trip_duration_days)

    def packages_needed_for_data(
        self,
        trip_duration_days: int,
        target_data_gb: NumericInput,
    ) -> int:
        """Number of packages required to cover both duration and target data."""
        return _normalization.packages_needed_for_data(self, trip_duration_days, target_data_gb)

    def total_cost_local(self, trip_duration_days: int) -> Decimal:
        """Imputed total local-currency cost for the trip duration."""
        return _normalization.total_cost_local(self, trip_duration_days)

    def total_cost_usd(self, trip_duration_days: int) -> Decimal:
        """Imputed total USD reference cost for the trip duration."""
        return _normalization.total_cost_usd(self, trip_duration_days)

    def daily_cost_local(self, trip_duration_days: int) -> Decimal:
        """Effective local-currency cost per trip day."""
        return _normalization.daily_cost_local(self, trip_duration_days)

    def daily_cost_usd(self, trip_duration_days: int) -> Decimal:
        """Effective USD cost per trip day."""
        return _normalization.daily_cost_usd(self, trip_duration_days)

    def effective_cost_per_gb_local(
        self,
        trip_duration_days: int,
        target_data_gb: NumericInput,
    ) -> Decimal:
        """Effective local-currency cost per usable GB."""
        return _normalization.effective_cost_per_gb_local(
            self, trip_duration_days, target_data_gb
        )

    def effective_cost_per_gb_usd(
        self,
        trip_duration_days: int,
        target_data_gb: NumericInput,
    ) -> Decimal:
        """Effective USD cost per usable GB."""
        return _normalization.effective_cost_per_gb_usd(self, trip_duration_days, target_data_gb)

    def friction_breakdown(self) -> FrictionScore:
        """Detailed five-factor friction score breakdown."""
        return _friction.calculate_friction_breakdown(self)

    def friction_score(self) -> Decimal:
        """Scalar operational friction score in [0, 100]."""
        return _friction.friction_score(self)

    @property
    def is_verified(self) -> bool:
        """Return True only when both last_verified_at and verification_source_url are non-empty."""
        return (
            isinstance(self.last_verified_at, str)
            and bool(self.last_verified_at.strip())
            and isinstance(self.verification_source_url, str)
            and bool(self.verification_source_url.strip())
        )

    def freshness_status(self, reference_time: datetime) -> FreshnessStatus:
        """Freshness classification relative to an explicit reference timestamp."""
        return _normalization.freshness_status(self.last_verified_at, reference_time)


Option = ServiceOption
