"""Regression tests for defects found by the independent cross-review."""
from __future__ import annotations

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest
from test_scenarios_and_simulate import InMemoryOptionRepository, _make_traveler

from travel_sim.application.simulate import SimulationRequest, simulate
from travel_sim.domain import (
    City,
    DeviceProfile,
    PaymentMethodPreference,
    ScenarioType,
    ServiceCategory,
    SimType,
)
from travel_sim.infrastructure.json_repository import (
    JsonOptionRepository,
    RepositoryValidationError,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "travel_sim"


def _city() -> City:
    return City(
        id="scl",
        name="Santiago",
        country_code="CL",
        local_currency="CLP",
        default_usd_exchange_rate=Decimal(950),
        last_verified_at="2026-11-20T00:00:00Z",
    )


def test_filter_alone_keeps_cheaper_physical_sim_away_from_esim_only_device(make_option) -> None:
    """The physical chip is strictly cheaper AND lower friction: only the filter excludes it."""
    phys = make_option(
        id="conn-phys",
        city_id="scl",
        sim_type=SimType.PHYSICAL_SIM,
        cost_local_currency=Decimal(1000),
        cost_usd_reference=Decimal(1),
        setup_time_minutes=0,
    )
    esim = make_option(
        id="conn-esim",
        city_id="scl",
        sim_type=SimType.ESIM,
        cost_local_currency=Decimal(50000),
        cost_usd_reference=Decimal(50),
        setup_time_minutes=30,
    )
    repo = InMemoryOptionRepository(_city(), (phys, esim))
    traveler = _make_traveler(
        device_profile=DeviceProfile.esim_only(),
        target_data_gb=Decimal(5),
    )

    result = simulate(repo, traveler=traveler, categories=(ServiceCategory.CONNECTIVITY,))

    for scenario_type in ScenarioType:
        choice = result.scenarios[scenario_type].choice_for(ServiceCategory.CONNECTIVITY)
        assert choice is not None
        assert choice.option.id == "conn-esim"


def test_request_with_traveler_keeps_the_traveler_fields(make_option) -> None:
    option = make_option(id="conn-esim", city_id="scl")
    repo = InMemoryOptionRepository(_city(), (option,))
    traveler = _make_traveler(
        trip_duration_days=30,
        target_data_gb=Decimal(20),
        payment_method_preference=PaymentMethodPreference.CASH,
    )

    result = simulate(repo, SimulationRequest(traveler=traveler))

    assert result.traveler.trip_duration_days == 30
    assert result.traveler.target_data_gb == Decimal(20)
    assert result.traveler.payment_method_preference == PaymentMethodPreference.CASH


def test_required_categories_without_catalog_rows_are_reported(make_option) -> None:
    option = make_option(id="conn-esim", city_id="scl")
    repo = InMemoryOptionRepository(_city(), (option,))

    result = simulate(repo, traveler=_make_traveler())

    assert ServiceCategory.CONNECTIVITY not in result.missing_categories
    assert len(result.missing_categories) >= 1


def _write_city_file(tmp_path: Path, *, option_overrides: dict) -> Path:
    seed = json.loads(
        (PACKAGE_ROOT.parent / "data" / "cities" / "santiago.json").read_text(encoding="utf-8")
    )
    connectivity = next(o for o in seed["options"] if o["category"] == "CONNECTIVITY")
    connectivity.update(option_overrides)
    path = tmp_path / "city.json"
    path.write_text(json.dumps(seed), encoding="utf-8")
    return path


def test_connectivity_option_without_a_sim_type_is_rejected_at_load(tmp_path: Path) -> None:
    path = _write_city_file(tmp_path, option_overrides={"sim_type": "NOT_APPLICABLE"})
    with pytest.raises(RepositoryValidationError):
        JsonOptionRepository(path)


def test_duplicate_option_ids_are_rejected_at_load(tmp_path: Path) -> None:
    seed = json.loads(
        (PACKAGE_ROOT.parent / "data" / "cities" / "santiago.json").read_text(encoding="utf-8")
    )
    seed["options"].append(dict(seed["options"][0]))
    path = tmp_path / "city.json"
    path.write_text(json.dumps(seed), encoding="utf-8")
    with pytest.raises(RepositoryValidationError):
        JsonOptionRepository(path)


def test_option_with_date_but_empty_source_is_not_verified(make_option) -> None:
    unsourced = make_option(
        last_verified_at="2026-11-01T00:00:00Z",
        verification_source_url="",
    )
    sourced = make_option(
        last_verified_at="2026-11-01T00:00:00Z",
        verification_source_url="https://example.invalid/source",
    )
    assert unsourced.is_verified is False
    assert sourced.is_verified is True


def test_application_layer_never_imports_infrastructure() -> None:
    offenders = []
    for path in (PACKAGE_ROOT / "application").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = ",".join(alias.name for alias in node.names)
            if module and "infrastructure" in module:
                offenders.append(f"{path.name}: {module}")
    assert offenders == []


def test_assistant_answering_only_nulls_never_beats_the_local_optimum() -> None:
    from travel_sim.application.audit import run_audit

    class AllNullAssistant:
        def ask(self, prompt: str, salt: str) -> str:
            return json.dumps(
                {
                    "CONNECTIVITY": None,
                    "AIRPORT_TRANSFER": None,
                    "URBAN_TRANSIT": None,
                    "DAY_TRIP": None,
                    "DINING": None,
                }
            )

    repo = JsonOptionRepository(PACKAGE_ROOT.parent / "data" / "cities")
    traveler = _make_traveler(target_data_gb=Decimal(5))

    report = run_audit(repo, traveler, {"nulls": AllNullAssistant()}, replications=1)
    score = report.assistants["nulls"].replications[0].score

    assert score is not None
    assert score.total_cost_usd > 0
    assert score.overpayment_vs_local_usd >= 0
