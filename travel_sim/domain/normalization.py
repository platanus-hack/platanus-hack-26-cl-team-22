"""Unit normalization and freshness helpers per docs/travel-simulator/data-model.md."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import TYPE_CHECKING

from travel_sim.domain.enums import FreshnessStatus, PricingModel, ServiceCategory
from travel_sim.domain.value_objects import NumericInput, to_decimal

if TYPE_CHECKING:
    from travel_sim.domain.entities import ServiceOption

FRESH_MAX_AGE_DAYS = 60
STALE_MAX_AGE_DAYS = 180


def _validate_trip_duration_days(trip_duration_days: int) -> int:
    if isinstance(trip_duration_days, bool) or not isinstance(trip_duration_days, int):
        raise TypeError("trip_duration_days must be an int")
    if trip_duration_days < 1:
        raise ValueError(f"trip_duration_days must be >= 1, got {trip_duration_days}")
    return trip_duration_days


def _ceil_div_int(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def _ceil_div_decimal(numerator: Decimal, denominator: Decimal) -> int:
    quotient = (numerator / denominator).to_integral_value(rounding=ROUND_CEILING)
    return int(quotient)


def packages_needed(option: ServiceOption, trip_duration_days: int) -> int:
    """Return the number of billable units/packages needed for the trip duration.

    - ONE_TIME_PACKAGE / VARIABLE_USAGE: ceil(trip_duration_days / validity_days)
    - PER_DAY: trip_duration_days
    - PER_TRIP: 1
    """
    days = _validate_trip_duration_days(trip_duration_days)
    if option.pricing_model == PricingModel.PER_DAY:
        return days
    if option.pricing_model == PricingModel.PER_TRIP:
        return 1
    return _ceil_div_int(days, option.validity_days)


def packages_needed_for_data(
    option: ServiceOption,
    trip_duration_days: int,
    target_data_gb: NumericInput,
) -> int:
    """Return packages needed to cover both trip duration and target data volume.

    Used for engine-spec.md section 2.1 rule 4 when a connectivity option allows
    stacking/top-ups across packages.
    """
    base_packages = packages_needed(option, trip_duration_days)
    target_gb = to_decimal(target_data_gb, "target_data_gb")
    if target_gb < 0:
        raise ValueError(f"target_data_gb must be >= 0, got {target_gb}")

    if (
        option.category != ServiceCategory.CONNECTIVITY
        or option.data_quota_gb is None
        or target_gb == 0
    ):
        return base_packages

    if option.data_quota_gb == 0:
        raise ValueError("cannot satisfy positive target_data_gb with a 0 GB quota option")

    data_packages = _ceil_div_decimal(target_gb, option.data_quota_gb)
    return max(base_packages, data_packages)


def total_cost_local(option: ServiceOption, trip_duration_days: int) -> Decimal:
    """Imputed total cost in local currency for the trip duration."""
    return Decimal(packages_needed(option, trip_duration_days)) * option.cost_local_currency


def total_cost_usd(option: ServiceOption, trip_duration_days: int) -> Decimal:
    """Imputed total cost in USD reference currency for the trip duration."""
    return Decimal(packages_needed(option, trip_duration_days)) * option.cost_usd_reference


def daily_cost_local(option: ServiceOption, trip_duration_days: int) -> Decimal:
    """Effective cost per trip day in local currency."""
    days = _validate_trip_duration_days(trip_duration_days)
    return total_cost_local(option, days) / Decimal(days)


def daily_cost_usd(option: ServiceOption, trip_duration_days: int) -> Decimal:
    """Effective cost per trip day in USD."""
    days = _validate_trip_duration_days(trip_duration_days)
    return total_cost_usd(option, days) / Decimal(days)


def _effective_usable_gb(
    option: ServiceOption,
    trip_duration_days: int,
    target_data_gb: NumericInput,
) -> Decimal:
    target_gb = to_decimal(target_data_gb, "target_data_gb")
    if target_gb <= 0:
        raise ValueError(f"target_data_gb must be > 0, got {target_gb}")
    if option.data_quota_gb is None or option.data_quota_gb <= 0:
        raise ValueError("effective cost per GB requires an option with data_quota_gb > 0")

    pkgs = packages_needed(option, trip_duration_days)
    total_quota = option.data_quota_gb * Decimal(pkgs)
    return min(target_gb, total_quota)


def effective_cost_per_gb_usd(
    option: ServiceOption,
    trip_duration_days: int,
    target_data_gb: NumericInput,
) -> Decimal:
    """Effective cost per usable GB in USD per data-model.md section 4.3."""
    usable_gb = _effective_usable_gb(option, trip_duration_days, target_data_gb)
    return total_cost_usd(option, trip_duration_days) / usable_gb


def effective_cost_per_gb_local(
    option: ServiceOption,
    trip_duration_days: int,
    target_data_gb: NumericInput,
) -> Decimal:
    """Effective cost per usable GB in local currency per data-model.md section 4.3."""
    usable_gb = _effective_usable_gb(option, trip_duration_days, target_data_gb)
    return total_cost_local(option, trip_duration_days) / usable_gb


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def freshness_status(last_verified_at: str, reference_time: datetime) -> FreshnessStatus:
    """Classify record freshness deterministically relative to reference_time.

    Thresholds (data-model.md section 6):
      - FRESH:   verified <= 60 days ago
      - STALE:   verified > 60 and <= 180 days ago
      - EXPIRED: verified > 180 days ago
    """
    verified_dt = _ensure_utc(datetime.fromisoformat(last_verified_at))
    ref_dt = _ensure_utc(reference_time)
    age = ref_dt - verified_dt
    if age < timedelta(0):
        raise ValueError("last_verified_at cannot be later than reference_time")
    if age <= timedelta(days=FRESH_MAX_AGE_DAYS):
        return FreshnessStatus.FRESH
    if age <= timedelta(days=STALE_MAX_AGE_DAYS):
        return FreshnessStatus.STALE
    return FreshnessStatus.EXPIRED
