"""Domain enumerations for the deterministic travel cost-vs-friction engine."""
from __future__ import annotations

from enum import Enum


class SimType(str, Enum):
    """SIM format required by a connectivity service option."""

    PHYSICAL_SIM = "PHYSICAL_SIM"
    ESIM = "ESIM"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ServiceCategory(str, Enum):
    """City-agnostic travel service categories."""

    CONNECTIVITY = "CONNECTIVITY"
    AIRPORT_TRANSFER = "AIRPORT_TRANSFER"
    URBAN_TRANSIT = "URBAN_TRANSIT"
    DAY_TRIP = "DAY_TRIP"
    DINING = "DINING"
    CURRENCY_EXCHANGE = "CURRENCY_EXCHANGE"


class PricingModel(str, Enum):
    """Billing unit model for a service option."""

    ONE_TIME_PACKAGE = "ONE_TIME_PACKAGE"
    PER_DAY = "PER_DAY"
    PER_TRIP = "PER_TRIP"
    VARIABLE_USAGE = "VARIABLE_USAGE"


class FrictionTolerance(str, Enum):
    """Qualitative traveler tolerance for operational friction."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DiningPreference(str, Enum):
    """Traveler dining tier preference."""

    BUDGET_LOCAL = "BUDGET_LOCAL"
    CASUAL = "CASUAL"
    TOURIST = "TOURIST"


class PaymentMethodPreference(str, Enum):
    """Traveler preferred payment method.

    CASH_ONLY is an alias for CASH so both data-model.md (CASH) and
    engine-spec.md (CASH_ONLY) resolve to the same canonical member.
    """

    INTERNATIONAL_CARD = "INTERNATIONAL_CARD"
    CASH = "CASH"
    CASH_ONLY = "CASH"  # noqa: PIE796 (intentional alias)
    MIXED = "MIXED"


class FreshnessStatus(str, Enum):
    """Verification freshness state derived from last_verified_at."""

    FRESH = "FRESH"
    STALE = "STALE"
    EXPIRED = "EXPIRED"


class ScenarioType(str, Enum):
    """Simulation scenario archetypes."""

    ZERO_FRICTION = "ZERO_FRICTION"
    BALANCED = "BALANCED"
    LOCAL_OPTIMIZED = "LOCAL_OPTIMIZED"
