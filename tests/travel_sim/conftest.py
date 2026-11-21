"""Synthetic pytest fixtures for travel_sim unit tests (no real-world prices)."""
from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from travel_sim.domain import (
    DeviceProfile,
    DiningPreference,
    FrictionTolerance,
    PaymentMethodPreference,
    PricingModel,
    ServiceCategory,
    ServiceOption,
    SimType,
    TravelerProfile,
)


def _build_option(**overrides: object) -> ServiceOption:
    defaults: dict[str, object] = {
        "id": "opt-default",
        "city_id": "city-test",
        "category": ServiceCategory.CONNECTIVITY,
        "provider": "SyntheticProvider",
        "name": "Synthetic Plan",
        "cost_local_currency": Decimal(10000),
        "cost_usd_reference": Decimal(10),
        "pricing_model": PricingModel.ONE_TIME_PACKAGE,
        "validity_days": 30,
        "data_quota_gb": Decimal(20),
        "setup_time_minutes": 0,
        "paperwork_level": 0,
        "language_barrier_level": 0,
        "physical_presence_required": False,
        "uncertainty_risk_level": 0,
        "requires_local_id": False,
        "sim_type": SimType.ESIM,
        "is_tourist_friendly": True,
        "last_verified_at": "2026-11-01T00:00:00Z",
        "verification_source_url": "https://example.invalid/source",
        "notes": "",
        "requires_international_card": False,
        "allows_top_up": True,
        "incompatible_option_ids": frozenset(),
    }
    defaults.update(overrides)
    return ServiceOption(**defaults)  # type: ignore[arg-type]


def _build_traveler(**overrides: object) -> TravelerProfile:
    defaults: dict[str, object] = {
        "id": "traveler-1",
        "destination_city_id": "city-test",
        "trip_duration_days": 7,
        "has_local_id": False,
        "target_data_gb": Decimal(10),
        "friction_tolerance": FrictionTolerance.MEDIUM,
        "device_profile": DeviceProfile.dual_sim(),
        "include_day_trips": True,
        "dining_preference": DiningPreference.CASUAL,
        "payment_method_preference": PaymentMethodPreference.MIXED,
    }
    defaults.update(overrides)
    return TravelerProfile(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def make_option() -> Callable[..., ServiceOption]:
    return _build_option


@pytest.fixture
def make_traveler() -> Callable[..., TravelerProfile]:
    return _build_traveler


@pytest.fixture
def esim_only_traveler() -> TravelerProfile:
    return _build_traveler(
        id="traveler-esim-only",
        has_local_id=False,
        device_profile=DeviceProfile.esim_only(),
    )


@pytest.fixture
def physical_sim_only_traveler() -> TravelerProfile:
    return _build_traveler(
        id="traveler-phys-only",
        has_local_id=False,
        device_profile=DeviceProfile.physical_sim_only(),
    )
