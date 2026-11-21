"""Application ports for destination and service option persistence."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from travel_sim.domain import (
    City,
    FreshnessStatus,
    ServiceCategory,
    ServiceOption,
)


@runtime_checkable
class OptionRepository(Protocol):
    """Port for catalog persistence and freshness-aware retrieval."""

    def list_cities(self) -> Sequence[City]:
        """List all available destination cities."""
        ...

    def get_city(self, city_id: str) -> City | None:
        """Retrieve city metadata by identifier."""
        ...

    def list_options(
        self,
        city_id: str,
        category: ServiceCategory | None = None,
    ) -> Sequence[ServiceOption]:
        """List options for a city, optionally filtered by service category."""
        ...

    def list_options_by_city_and_category(
        self,
        city_id: str,
        category: ServiceCategory,
    ) -> Sequence[ServiceOption]:
        """List options strictly matching the given city and category."""
        ...

    def get_option(self, option_id: str) -> ServiceOption | None:
        """Retrieve a specific service option by its unique identifier."""
        ...

    def is_verified(self, option_id: str) -> bool:
        """Return True if the option has verified metadata (last_verified_at is not None)."""
        ...

    def get_freshness_status(
        self,
        option_id: str,
        reference_time: datetime | None = None,
    ) -> FreshnessStatus | None:
        """Return freshness classification for a verified option, or None if unverified."""
        ...

    def list_unverified_options(
        self,
        city_id: str | None = None,
    ) -> Sequence[ServiceOption]:
        """Return options whose verification status is unverified (last_verified_at is None)."""
        ...


@runtime_checkable
class AssistantPort(Protocol):
    """Port for querying an AI assistant with a deterministic prompt and replication salt."""

    def ask(self, prompt: str, salt: str) -> str:
        """Send prompt with replication salt and return the raw assistant reply string."""
        ...

