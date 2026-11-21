"""Determinism and Clean Architecture boundary tests for travel_sim."""
from __future__ import annotations

import ast
import sys
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from travel_sim.application.filters import (
    apply_hard_filters,
    apply_soft_filters,
    local_optimized_scorer,
    zero_friction_scorer,
)
from travel_sim.domain import (
    DeviceProfile,
    ServiceOption,
    SimType,
    TravelerProfile,
    daily_cost_usd,
    effective_cost_per_gb_usd,
    friction_score,
    scenario_friction_score,
)


def test_domain_and_filter_calculations_are_deterministic(
    make_option: Callable[..., ServiceOption],
    make_traveler: Callable[..., TravelerProfile],
) -> None:
    traveler = make_traveler(
        trip_duration_days=9,
        target_data_gb=Decimal(12),
        has_local_id=False,
        device_profile=DeviceProfile.esim_only(),
    )
    options = [
        make_option(
            id="opt-b",
            cost_usd_reference=Decimal(12),
            setup_time_minutes=15,
            paperwork_level=1,
            sim_type=SimType.ESIM,
        ),
        make_option(
            id="opt-a",
            cost_usd_reference=Decimal(12),
            setup_time_minutes=15,
            paperwork_level=1,
            sim_type=SimType.ESIM,
        ),
        make_option(
            id="opt-rejected-phys",
            cost_usd_reference=Decimal(5),
            sim_type=SimType.PHYSICAL_SIM,
        ),
        make_option(
            id="opt-rejected-rut",
            cost_usd_reference=Decimal(4),
            requires_local_id=True,
        ),
    ]

    first_hard = apply_hard_filters(options, traveler)
    first_zf = apply_soft_filters(first_hard.eligible, traveler, scorer=zero_friction_scorer)
    first_lo = apply_soft_filters(first_hard.eligible, traveler, scorer=local_optimized_scorer)
    # Reversed input order with tied scores must still sort deterministically by option.id.
    reversed_zf = apply_soft_filters(
        list(reversed(first_hard.eligible)), traveler, scorer=zero_friction_scorer
    )
    assert [s.criteria.option.id for s in first_zf] == ["opt-a", "opt-b"]
    assert reversed_zf == first_zf

    for _ in range(10):
        assert apply_hard_filters(options, traveler) == first_hard
        assert apply_soft_filters(first_hard.eligible, traveler, scorer=zero_friction_scorer) == (
            first_zf
        )
        assert apply_soft_filters(
            first_hard.eligible, traveler, scorer=local_optimized_scorer
        ) == first_lo
        assert [friction_score(o) for o in options] == [friction_score(o) for o in options]
        assert scenario_friction_score(first_hard.eligible) == scenario_friction_score(
            first_hard.eligible
        )
        assert daily_cost_usd(options[0], 9) == daily_cost_usd(options[0], 9)
        assert effective_cost_per_gb_usd(options[0], 9, Decimal(12)) == (
            effective_cost_per_gb_usd(options[0], 9, Decimal(12))
        )


def test_domain_layer_imports_only_stdlib_and_domain() -> None:
    domain_dir = Path(__file__).resolve().parents[2] / "travel_sim" / "domain"
    py_files = sorted(domain_dir.glob("*.py"))
    assert py_files, "expected domain modules under travel_sim/domain/"

    allowed_roots = set(sys.stdlib_module_names) | {"travel_sim"}
    forbidden_prefixes = (
        "travel_sim.application",
        "travel_sim.infrastructure",
        "travel_sim.adapters",
    )

    for path in py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    assert root in allowed_roots, f"{path.name} imports non-stdlib {alias.name}"
                    assert not alias.name.startswith(forbidden_prefixes), (
                        f"{path.name} violates layer boundary: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                root = node.module.split(".", 1)[0]
                assert root in allowed_roots, f"{path.name} imports non-stdlib {node.module}"
                assert not node.module.startswith(forbidden_prefixes), (
                    f"{path.name} violates layer boundary: {node.module}"
                )
