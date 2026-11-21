"""Unit tests for unit normalization math, Money value object, and freshness."""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from travel_sim.domain import (
    City,
    FreshnessStatus,
    Money,
    Option,
    PricingModel,
    ServiceCategory,
    ServiceOption,
    SimType,
    daily_cost_local,
    daily_cost_usd,
    effective_cost_per_gb_local,
    effective_cost_per_gb_usd,
    freshness_status,
    packages_needed,
    packages_needed_for_data,
    total_cost_local,
    total_cost_usd,
)


def test_option_alias_matches_service_option() -> None:
    assert Option is ServiceOption


def test_one_time_package_ceiling_and_daily_normalization(
    make_option: Callable[..., ServiceOption],
) -> None:
    opt = make_option(
        pricing_model=PricingModel.ONE_TIME_PACKAGE,
        validity_days=7,
        cost_local_currency=Decimal(9000),
        cost_usd_reference=Decimal(10),
    )
    assert packages_needed(opt, 1) == 1
    assert packages_needed(opt, 7) == 1
    assert packages_needed(opt, 8) == 2
    assert packages_needed(opt, 14) == 2
    assert packages_needed(opt, 15) == 3

    assert total_cost_usd(opt, 10) == Decimal(20)
    assert total_cost_local(opt, 10) == Decimal(18000)
    assert daily_cost_usd(opt, 10) == Decimal(2)
    assert daily_cost_local(opt, 10) == Decimal(1800)

    assert opt.packages_needed(10) == 2
    assert opt.total_cost_usd(10) == Decimal(20)
    assert opt.daily_cost_usd(10) == Decimal(2)


def test_per_day_and_per_trip_pricing_models(
    make_option: Callable[..., ServiceOption],
) -> None:
    daily_opt = make_option(
        category=ServiceCategory.DINING,
        sim_type=SimType.NOT_APPLICABLE,
        data_quota_gb=None,
        pricing_model=PricingModel.PER_DAY,
        validity_days=1,
        cost_local_currency=Decimal(5000),
        cost_usd_reference=Decimal(5),
    )
    assert packages_needed(daily_opt, 6) == 6
    assert total_cost_usd(daily_opt, 6) == Decimal(30)
    assert daily_cost_usd(daily_opt, 6) == Decimal(5)

    trip_opt = make_option(
        category=ServiceCategory.AIRPORT_TRANSFER,
        sim_type=SimType.NOT_APPLICABLE,
        data_quota_gb=None,
        pricing_model=PricingModel.PER_TRIP,
        validity_days=1,
        cost_local_currency=Decimal(15000),
        cost_usd_reference=Decimal(15),
    )
    assert packages_needed(trip_opt, 10) == 1
    assert total_cost_usd(trip_opt, 10) == Decimal(15)
    assert daily_cost_usd(trip_opt, 10) == Decimal("1.5")


def test_effective_cost_per_gb_uses_min_of_target_and_supplied_quota(
    make_option: Callable[..., ServiceOption],
) -> None:
    # Target (10 GB) < supplied quota (100 GB): denominator is target (10 GB).
    large_bundle = make_option(
        validity_days=30,
        data_quota_gb=Decimal(100),
        cost_local_currency=Decimal(9500),
        cost_usd_reference=Decimal(10),
    )
    assert effective_cost_per_gb_usd(large_bundle, 7, Decimal(10)) == Decimal(1)
    assert effective_cost_per_gb_local(large_bundle, 7, Decimal(10)) == Decimal(950)
    assert large_bundle.effective_cost_per_gb_usd(7, Decimal(10)) == Decimal(1)

    # Target (20 GB) > supplied quota in 1 package (5 GB): denominator is 5 GB.
    small_bundle = make_option(
        validity_days=30,
        data_quota_gb=Decimal(5),
        cost_local_currency=Decimal(4000),
        cost_usd_reference=Decimal(10),
    )
    assert effective_cost_per_gb_usd(small_bundle, 7, Decimal(20)) == Decimal(2)
    assert effective_cost_per_gb_local(small_bundle, 7, Decimal(20)) == Decimal(800)

    # Multi-package duration: 2 packages x 5 GB = 10 GB supplied vs 8 GB target.
    short_bundle = make_option(
        validity_days=5,
        data_quota_gb=Decimal(5),
        cost_local_currency=Decimal(4000),
        cost_usd_reference=Decimal(4),
    )
    assert packages_needed(short_bundle, 8) == 2
    assert effective_cost_per_gb_usd(short_bundle, 8, Decimal(8)) == Decimal(1)


def test_packages_needed_for_data_stacks_when_quota_below_target(
    make_option: Callable[..., ServiceOption],
) -> None:
    opt = make_option(validity_days=30, data_quota_gb=Decimal(3))
    assert packages_needed_for_data(opt, 5, Decimal(10)) == 4
    assert packages_needed_for_data(opt, 5, Decimal(9)) == 3
    assert packages_needed_for_data(opt, 40, Decimal(2)) == 2


def test_normalization_rejects_invalid_arguments(
    make_option: Callable[..., ServiceOption],
) -> None:
    opt = make_option(
        data_quota_gb=None,
        category=ServiceCategory.DINING,
        sim_type=SimType.NOT_APPLICABLE,
    )
    with pytest.raises(ValueError):
        packages_needed(opt, 0)
    with pytest.raises(ValueError):
        effective_cost_per_gb_usd(opt, 5, Decimal(5))

    conn_opt = make_option(data_quota_gb=Decimal(10))
    with pytest.raises(ValueError):
        effective_cost_per_gb_usd(conn_opt, 5, Decimal(0))


def test_freshness_status_thresholds() -> None:
    ref = datetime(2026, 11, 21, 0, 0, 0, tzinfo=UTC)
    assert freshness_status("2026-11-21T00:00:00Z", ref) == FreshnessStatus.FRESH
    assert freshness_status("2026-09-22T00:00:00Z", ref) == FreshnessStatus.FRESH  # 60 days
    assert freshness_status("2026-09-21T00:00:00Z", ref) == FreshnessStatus.STALE  # 61 days
    assert freshness_status("2026-05-25T00:00:00Z", ref) == FreshnessStatus.STALE  # 180 days
    assert freshness_status("2026-05-24T00:00:00Z", ref) == FreshnessStatus.EXPIRED  # 181 days

    with pytest.raises(ValueError):
        freshness_status("2026-11-22T00:00:00Z", ref)


def test_money_value_object_and_city_validation() -> None:
    usd_10 = Money(Decimal(10), "usd")
    usd_25 = Money(Decimal("25.50"), "USD")
    clp = Money(Decimal(1000), "CLP")

    assert usd_10.currency == "USD"
    assert (usd_10 + usd_25) == Money(Decimal("35.50"), "USD")
    assert (usd_25 - usd_10) == Money(Decimal("15.50"), "USD")
    assert (usd_10 * 3) == Money(Decimal(30), "USD")
    assert (usd_10 / 4) == Money(Decimal("2.5"), "USD")
    assert usd_10 < usd_25

    with pytest.raises(ValueError):
        _ = usd_10 + clp
    with pytest.raises(ZeroDivisionError):
        _ = usd_10 / 0

    city = City(
        id="city-test",
        name="Testville",
        country_code="cl",
        local_currency="clp",
        default_usd_exchange_rate=Decimal(1000),
        last_verified_at="2026-11-01T00:00:00Z",
    )
    assert city.country_code == "CL"
    assert city.local_currency == "CLP"
