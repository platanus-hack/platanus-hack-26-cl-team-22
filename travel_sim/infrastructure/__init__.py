"""Infrastructure layer adapters for the travel cost-vs-friction engine."""
from __future__ import annotations

from travel_sim.infrastructure.json_repository import (
    JsonOptionRepository,
    RepositoryValidationError,
)

__all__ = [
    "JsonOptionRepository",
    "RepositoryValidationError",
]
