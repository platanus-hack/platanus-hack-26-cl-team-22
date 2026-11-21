"""Unit and integration tests for JsonOptionRepository and OptionRepository port."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from travel_sim.application.ports import OptionRepository
from travel_sim.domain import (
    FreshnessStatus,
    ServiceCategory,
    SimType,
)
from travel_sim.infrastructure.json_repository import (
    JsonOptionRepository,
    RepositoryValidationError,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SANTIAGO_SEED_PATH = REPO_ROOT / "data" / "cities" / "santiago.json"


def _build_valid_payload() -> dict[str, object]:
    return {
        "city": {
            "id": "test-city",
            "name": "Test City",
            "country_code": "CL",
            "local_currency": "CLP",
            "default_usd_exchange_rate": 950.0,
            "last_verified_at": "2026-11-20T00:00:00Z",
        },
        "options": [
            {
                "id": "test-opt-1",
                "city_id": "test-city",
                "category": "CONNECTIVITY",
                "provider": "TestProvider",
                "name": "Test Plan",
                "cost_local_currency": 10000,
                "cost_usd_reference": 10.50,
                "pricing_model": "ONE_TIME_PACKAGE",
                "validity_days": 30,
                "data_quota_gb": 50.0,
                "setup_time_minutes": 10,
                "paperwork_level": 1,
                "language_barrier_level": 0,
                "physical_presence_required": False,
                "uncertainty_risk_level": 0,
                "requires_local_id": False,
                "sim_type": "ESIM",
                "is_tourist_friendly": True,
                "last_verified_at": None,
                "verification_source_url": "https://example.invalid",
                "notes": "Test notes",
                "requires_international_card": False,
                "allows_top_up": True,
                "incompatible_option_ids": [],
            }
        ],
    }


# 1. Loading the seed


def test_loading_santiago_seed() -> None:
    repo = JsonOptionRepository(SANTIAGO_SEED_PATH)

    cities = repo.list_cities()
    assert len(cities) == 1
    city = cities[0]
    assert city.id == "scl"
    assert city.name == "Santiago"
    assert city.country_code == "CL"
    assert city.local_currency == "CLP"
    assert city.default_usd_exchange_rate == Decimal(950)

    options = repo.list_options("scl")
    assert len(options) == 13

    # Check category distribution
    connectivity = repo.list_options_by_city_and_category("scl", ServiceCategory.CONNECTIVITY)
    transfers = repo.list_options_by_city_and_category("scl", ServiceCategory.AIRPORT_TRANSFER)
    transit = repo.list_options_by_city_and_category("scl", ServiceCategory.URBAN_TRANSIT)
    day_trips = repo.list_options_by_city_and_category("scl", ServiceCategory.DAY_TRIP)

    assert len(connectivity) == 4
    assert len(transfers) == 3
    assert len(transit) == 2
    assert len(day_trips) == 2

    # Verify key attributes from seeding strategy
    wom_esim = repo.get_option("scl-conn-wom-plan-zero-esim")
    assert wom_esim is not None
    assert wom_esim.provider == "WOM"
    assert wom_esim.sim_type == SimType.ESIM
    assert wom_esim.data_quota_gb == Decimal(100)
    assert wom_esim.cost_local_currency == Decimal(9990)
    assert wom_esim.cost_usd_reference == Decimal("10.52")
    assert not wom_esim.physical_presence_required
    assert not wom_esim.requires_local_id

    entel_chip = repo.get_option("scl-conn-entel-chip-fisico")
    assert entel_chip is not None
    assert entel_chip.sim_type == SimType.PHYSICAL_SIM
    assert entel_chip.uncertainty_risk_level == 2
    assert entel_chip.physical_presence_required


# 2. Rejecting malformed input


def test_rejecting_unknown_enum_values() -> None:
    repo = JsonOptionRepository()

    bad_category = _build_valid_payload()
    bad_category["options"][0]["category"] = "INVALID_CATEGORY"
    with pytest.raises(RepositoryValidationError, match="Unknown ServiceCategory"):
        repo.load_dict(bad_category)

    bad_pricing = _build_valid_payload()
    bad_pricing["options"][0]["pricing_model"] = "LIFETIME"
    with pytest.raises(RepositoryValidationError, match="Unknown PricingModel"):
        repo.load_dict(bad_pricing)

    bad_sim = _build_valid_payload()
    bad_sim["options"][0]["sim_type"] = "QUANTUM_SIM"
    with pytest.raises(RepositoryValidationError, match="Unknown SimType"):
        repo.load_dict(bad_sim)


def test_rejecting_missing_required_fields() -> None:
    repo = JsonOptionRepository()

    for field in ("provider", "name", "cost_local_currency", "cost_usd_reference", "sim_type"):
        payload = _build_valid_payload()
        del payload["options"][0][field]
        with pytest.raises(RepositoryValidationError, match=f"Missing required field '{field}'"):
            repo.load_dict(payload)

    # Missing city definition
    no_city = {"options": []}
    with pytest.raises(RepositoryValidationError, match="Missing 'city' definition"):
        repo.load_dict(no_city)

    # Missing options field
    no_options = {"city": _build_valid_payload()["city"]}
    with pytest.raises(RepositoryValidationError, match="Missing 'options'"):
        repo.load_dict(no_options)


def test_rejecting_negative_money_and_invalid_numbers() -> None:
    repo = JsonOptionRepository()

    neg_local = _build_valid_payload()
    neg_local["options"][0]["cost_local_currency"] = -100
    with pytest.raises(RepositoryValidationError, match="cannot be negative"):
        repo.load_dict(neg_local)

    neg_usd = _build_valid_payload()
    neg_usd["options"][0]["cost_usd_reference"] = -5.0
    with pytest.raises(RepositoryValidationError, match="cannot be negative"):
        repo.load_dict(neg_usd)

    neg_rate = _build_valid_payload()
    neg_rate["city"]["default_usd_exchange_rate"] = -950
    with pytest.raises(RepositoryValidationError, match="default_usd_exchange_rate must be > 0"):
        repo.load_dict(neg_rate)


def test_rejecting_bad_dates() -> None:
    repo = JsonOptionRepository()

    bad_date_option = _build_valid_payload()
    bad_date_option["options"][0]["last_verified_at"] = "not-a-valid-date"
    with pytest.raises(RepositoryValidationError, match="Invalid ISO 8601 date"):
        repo.load_dict(bad_date_option)

    bad_city_date = _build_valid_payload()
    bad_city_date["city"]["last_verified_at"] = "2026/13/45"
    with pytest.raises(RepositoryValidationError, match="City last_verified_at has invalid ISO date"):
        repo.load_dict(bad_city_date)


# 3. Unverified options flagged


def test_unverified_options_flagged_in_seed() -> None:
    repo = JsonOptionRepository(SANTIAGO_SEED_PATH)

    options = repo.list_options("scl")
    assert len(options) == 13

    # Only options with a real source are verified; everything else must stay flagged unverified.
    verified_ids = {
        "scl-conn-wom-plan-zero-esim",
        "scl-transfer-centropuerto-bus",
        "scl-dining-menu-del-dia",
        "scl-dining-menu-ejecutivo",
    }
    for opt in options:
        if opt.id in verified_ids:
            assert repo.is_verified(opt.id) is True
            assert opt.verification_source_url.startswith("https://")
        else:
            assert repo.is_verified(opt.id) is False
            assert repo.get_freshness_status(opt.id) is None
            assert opt.last_verified_at is None

    unverified_options = repo.list_unverified_options("scl")
    assert len(unverified_options) == 9
    assert {opt.id for opt in unverified_options} == {opt.id for opt in options} - verified_ids


def test_verified_option_returns_freshness_status() -> None:
    repo = JsonOptionRepository()
    payload = _build_valid_payload()
    payload["options"][0]["last_verified_at"] = "2026-11-20T00:00:00Z"
    repo.load_dict(payload)

    opt_id = "test-opt-1"
    assert repo.is_verified(opt_id) is True
    assert len(repo.list_unverified_options("test-city")) == 0

    ref_time = datetime(2026, 11, 21, 0, 0, 0, tzinfo=UTC)
    status = repo.get_freshness_status(opt_id, reference_time=ref_time)
    assert status == FreshnessStatus.FRESH


# 4. Adding a second city file without changing code


def test_adding_second_city_file_without_changing_code(tmp_path: Path) -> None:
    santiago_file = tmp_path / "santiago.json"
    with SANTIAGO_SEED_PATH.open("r", encoding="utf-8") as f:
        santiago_data = json.load(f)
    with santiago_file.open("w", encoding="utf-8") as f:
        json.dump(santiago_data, f)

    # Second city: Buenos Aires
    second_city_data = {
        "city": {
            "id": "bue",
            "name": "Buenos Aires",
            "country_code": "AR",
            "local_currency": "ARS",
            "default_usd_exchange_rate": 1050.0,
            "last_verified_at": "2026-11-21T00:00:00Z",
        },
        "options": [
            {
                "id": "bue-subte-linea-d",
                "city_id": "bue",
                "category": "URBAN_TRANSIT",
                "provider": "Subte de Buenos Aires",
                "name": "Subte Línea D",
                "cost_local_currency": 750,
                "cost_usd_reference": 0.75,
                "pricing_model": "PER_TRIP",
                "validity_days": 1,
                "data_quota_gb": None,
                "setup_time_minutes": 5,
                "paperwork_level": 0,
                "language_barrier_level": 1,
                "physical_presence_required": True,
                "uncertainty_risk_level": 0,
                "requires_local_id": False,
                "sim_type": "NOT_APPLICABLE",
                "is_tourist_friendly": True,
                "last_verified_at": "2026-11-21T00:00:00Z",
                "verification_source_url": "",
                "notes": "Red Subte de Buenos Aires",
                "requires_international_card": False,
                "allows_top_up": False,
                "incompatible_option_ids": [],
            }
        ],
    }
    bue_file = tmp_path / "buenos_aires.json"
    with bue_file.open("w", encoding="utf-8") as f:
        json.dump(second_city_data, f)

    # Load directory containing both city files without changing any code
    repo = JsonOptionRepository(tmp_path)

    cities = repo.list_cities()
    city_ids = {c.id for c in cities}
    assert "scl" in city_ids
    assert "bue" in city_ids

    scl_opts = repo.list_options("scl")
    assert len(scl_opts) == 13
    assert all(o.city_id == "scl" for o in scl_opts)

    bue_opts = repo.list_options("bue")
    assert len(bue_opts) == 1
    assert bue_opts[0].id == "bue-subte-linea-d"
    assert bue_opts[0].city_id == "bue"
    assert bue_opts[0].cost_local_currency == Decimal(750)


# 5. Repository satisfies the port


def test_repository_satisfies_port() -> None:
    repo = JsonOptionRepository(SANTIAGO_SEED_PATH)

    # Verify runtime protocol conformance
    assert isinstance(repo, OptionRepository)

    # Verify all port methods are present and callable
    assert callable(repo.list_cities)
    assert callable(repo.get_city)
    assert callable(repo.list_options)
    assert callable(repo.list_options_by_city_and_category)
    assert callable(repo.get_option)
    assert callable(repo.is_verified)
    assert callable(repo.get_freshness_status)
    assert callable(repo.list_unverified_options)

    # Test query calls
    assert repo.get_city("scl") is not None
    assert repo.get_city("unknown-city") is None
    assert repo.get_option("scl-conn-wom-plan-zero-esim") is not None
    assert repo.get_option("unknown-option") is None
