"""Deterministic tests for the AI-assistant audit pipeline."""
from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal

import pytest

from travel_sim.application.audit import (
    AuditAIAssistantsUseCase,
    build_audit_prompt,
    compute_confidence_interval_95,
    parse_and_validate_reply,
    run_audit,
)
from travel_sim.application.filters import RejectionReason
from travel_sim.application.ports import AssistantPort
from travel_sim.domain import (
    DeviceProfile,
    DiningPreference,
    FrictionTolerance,
    PaymentMethodPreference,
    ServiceCategory,
    TravelerProfile,
    friction_score,
    scenario_friction_score,
)
from travel_sim.infrastructure.json_repository import JsonOptionRepository


class SequenceFakeAssistant:
    """Deterministic fake assistant cycling through scripted replies by call order."""

    def __init__(self, replies: Sequence[str]) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def ask(self, prompt: str, salt: str) -> str:
        idx = len(self.calls)
        self.calls.append((prompt, salt))
        return self._replies[idx]


def _build_synthetic_repo() -> JsonOptionRepository:
    payload = {
        "city": {
            "id": "city-test",
            "name": "Testopolis",
            "country_code": "CL",
            "local_currency": "CLP",
            "default_usd_exchange_rate": 1000.0,
            "last_verified_at": "2026-11-01T00:00:00Z",
        },
        "options": [
            {
                "id": "conn-local-esim",
                "city_id": "city-test",
                "category": "CONNECTIVITY",
                "provider": "LocalTel",
                "name": "Local eSIM 50GB",
                "cost_local_currency": 10000,
                "cost_usd_reference": 10,
                "pricing_model": "ONE_TIME_PACKAGE",
                "validity_days": 30,
                "data_quota_gb": 50.0,
                "setup_time_minutes": 30,
                "paperwork_level": 2,
                "language_barrier_level": 1,
                "physical_presence_required": False,
                "uncertainty_risk_level": 0,
                "requires_local_id": False,
                "sim_type": "ESIM",
                "is_tourist_friendly": True,
                "last_verified_at": "2026-11-01T00:00:00Z",
                "requires_international_card": False,
                "allows_top_up": True,
            },
            {
                "id": "conn-phys-rut",
                "city_id": "city-test",
                "category": "CONNECTIVITY",
                "provider": "LocalPhys",
                "name": "Local Physical SIM (RUT required)",
                "cost_local_currency": 8000,
                "cost_usd_reference": 8,
                "pricing_model": "ONE_TIME_PACKAGE",
                "validity_days": 30,
                "data_quota_gb": 50.0,
                "setup_time_minutes": 45,
                "paperwork_level": 2,
                "language_barrier_level": 1,
                "physical_presence_required": True,
                "uncertainty_risk_level": 0,
                "requires_local_id": True,
                "sim_type": "PHYSICAL_SIM",
                "is_tourist_friendly": False,
                "last_verified_at": "2026-11-01T00:00:00Z",
                "requires_international_card": False,
                "allows_top_up": True,
            },
            {
                "id": "conn-global-esim",
                "city_id": "city-test",
                "category": "CONNECTIVITY",
                "provider": "GlobalSim",
                "name": "Global Travel eSIM 5GB",
                "cost_local_currency": 20000,
                "cost_usd_reference": 20,
                "pricing_model": "ONE_TIME_PACKAGE",
                "validity_days": 7,
                "data_quota_gb": 5.0,
                "setup_time_minutes": 0,
                "paperwork_level": 0,
                "language_barrier_level": 0,
                "physical_presence_required": False,
                "uncertainty_risk_level": 0,
                "requires_local_id": False,
                "sim_type": "ESIM",
                "is_tourist_friendly": True,
                "last_verified_at": "2026-11-01T00:00:00Z",
                "requires_international_card": True,
                "allows_top_up": True,
            },
            {
                "id": "xfer-bus",
                "city_id": "city-test",
                "category": "AIRPORT_TRANSFER",
                "provider": "CityBus",
                "name": "Airport Public Bus",
                "cost_local_currency": 2000,
                "cost_usd_reference": 2,
                "pricing_model": "PER_TRIP",
                "validity_days": 1,
                "data_quota_gb": None,
                "setup_time_minutes": 30,
                "paperwork_level": 0,
                "language_barrier_level": 1,
                "physical_presence_required": True,
                "uncertainty_risk_level": 0,
                "requires_local_id": False,
                "sim_type": "NOT_APPLICABLE",
                "is_tourist_friendly": True,
                "last_verified_at": "2026-11-01T00:00:00Z",
                "requires_international_card": False,
                "allows_top_up": False,
            },
            {
                "id": "xfer-private",
                "city_id": "city-test",
                "category": "AIRPORT_TRANSFER",
                "provider": "PrivRide",
                "name": "Private Airport Transfer",
                "cost_local_currency": 25000,
                "cost_usd_reference": 25,
                "pricing_model": "PER_TRIP",
                "validity_days": 1,
                "data_quota_gb": None,
                "setup_time_minutes": 0,
                "paperwork_level": 0,
                "language_barrier_level": 0,
                "physical_presence_required": False,
                "uncertainty_risk_level": 0,
                "requires_local_id": False,
                "sim_type": "NOT_APPLICABLE",
                "is_tourist_friendly": True,
                "last_verified_at": "2026-11-01T00:00:00Z",
                "requires_international_card": True,
                "allows_top_up": False,
            },
        ],
    }
    repo = JsonOptionRepository()
    repo.load_dict(payload, source="<synthetic>")
    return repo


def _esim_tourist_traveler() -> TravelerProfile:
    return TravelerProfile(
        id="t-esim-tourist",
        destination_city_id="city-test",
        trip_duration_days=7,
        has_local_id=False,
        target_data_gb=Decimal(10),
        friction_tolerance=FrictionTolerance.MEDIUM,
        device_profile=DeviceProfile.esim_only(),
        include_day_trips=False,
        dining_preference=DiningPreference.CASUAL,
        payment_method_preference=PaymentMethodPreference.INTERNATIONAL_CARD,
    )


def test_prompt_is_deterministic_and_lists_closed_catalog() -> None:
    repo = _build_synthetic_repo()
    traveler = _esim_tourist_traveler()
    options = repo.list_options("city-test")
    city = repo.get_city("city-test")

    prompt_a = build_audit_prompt(traveler, options, city=city)
    prompt_b = build_audit_prompt(traveler, list(reversed(options)), city=city)

    assert prompt_a == prompt_b
    for opt in options:
        assert opt.id in prompt_a
    assert "CONNECTIVITY" in prompt_a
    assert "AIRPORT_TRANSFER" in prompt_a
    assert "supports_esim: true" in prompt_a
    assert "supports_physical_sim: false" in prompt_a


def test_parse_and_validate_reply_rejects_garbage_and_accepts_null() -> None:
    repo = _build_synthetic_repo()
    options = repo.list_options("city-test")
    categories = (ServiceCategory.CONNECTIVITY, ServiceCategory.AIRPORT_TRANSFER)

    garbage_replies = [
        "",
        "I suggest buying the global eSIM.",
        '```json\n{"CONNECTIVITY": "conn-global-esim", "AIRPORT_TRANSFER": "xfer-private"}\n```',
        '["conn-global-esim", "xfer-private"]',
        json.dumps({"CONNECTIVITY": "conn-global-esim"}),  # missing key
        json.dumps(
            {
                "CONNECTIVITY": "conn-global-esim",
                "AIRPORT_TRANSFER": "xfer-private",
                "EXTRA": "foo",
            }
        ),
        json.dumps({"CONNECTIVITY": "nonexistent-id", "AIRPORT_TRANSFER": "xfer-private"}),
        json.dumps({"CONNECTIVITY": "xfer-bus", "AIRPORT_TRANSFER": "xfer-private"}),  # wrong cat
        json.dumps({"CONNECTIVITY": ["conn-global-esim"], "AIRPORT_TRANSFER": "xfer-private"}),
    ]

    for reply in garbage_replies:
        parsed = parse_and_validate_reply(
            reply,
            catalog_options=options,
            expected_categories=categories,
            city_id="city-test",
        )
        assert not parsed.is_valid
        assert parsed.errors

    valid_with_null = parse_and_validate_reply(
        json.dumps({"CONNECTIVITY": "conn-local-esim", "AIRPORT_TRANSFER": None}),
        catalog_options=options,
        expected_categories=categories,
        city_id="city-test",
    )
    assert valid_with_null.is_valid
    assert valid_with_null.selections[ServiceCategory.CONNECTIVITY] is not None
    assert valid_with_null.selections[ServiceCategory.AIRPORT_TRANSFER] is None


def test_validity_accounting_infeasible_flagging_and_exact_overpayment() -> None:
    repo = _build_synthetic_repo()
    traveler = _esim_tourist_traveler()

    # Baselines for traveler (10 GB over 7 days, esim_only, no RUT):
    # - Local optimized: conn-local-esim ($10, 10000 CLP) + xfer-bus ($2, 2000 CLP)
    #   Total = $12 USD / 12000 CLP
    # - Zero friction: conn-global-esim (5GB/pkg -> 2 pkgs = $40, 40000 CLP) + xfer-private ($25, 25000 CLP)
    #   Total = $65 USD / 65000 CLP
    valid_expensive = json.dumps(
        {"CONNECTIVITY": "conn-global-esim", "AIRPORT_TRANSFER": "xfer-private"}
    )
    valid_cheaper = json.dumps(
        {"CONNECTIVITY": "conn-global-esim", "AIRPORT_TRANSFER": "xfer-bus"}
    )
    # Violates BOTH physical SIM (esim_only) and RUT (has_local_id=False)
    valid_infeasible = json.dumps(
        {"CONNECTIVITY": "conn-phys-rut", "AIRPORT_TRANSFER": "xfer-bus"}
    )

    replies = [
        "not json garbage",
        json.dumps({"CONNECTIVITY": "hallucinated-id", "AIRPORT_TRANSFER": "xfer-bus"}),
        valid_infeasible,
        valid_expensive,
        valid_cheaper,
    ]
    fake = SequenceFakeAssistant(replies)
    assert isinstance(fake, AssistantPort)

    report = run_audit(
        repo, traveler, {"fake-llm": fake}, replications=5, include_unverified=True
    )
    summary = report.assistants["fake-llm"]

    # Validity accounting: 3 valid out of 5 replications
    assert summary.total_replications == 5
    assert summary.valid_count == 3
    assert summary.invalid_count == 2
    assert summary.validity_rate == Decimal("0.6")

    # Feasibility accounting: 1 infeasible out of 3 valid replies (never silently fixed)
    assert summary.feasible_count == 2
    assert summary.infeasible_count == 1
    assert summary.infeasibility_rate == Decimal(1) / Decimal(3)

    rep_infeasible = summary.replications[2]
    assert rep_infeasible.is_valid is True
    assert rep_infeasible.is_feasible is False
    assert rep_infeasible.score is not None
    reasons = rep_infeasible.score.infeasibility_reasons[ServiceCategory.CONNECTIVITY]
    assert RejectionReason.UNSUPPORTED_PHYSICAL_SIM in reasons
    assert RejectionReason.REQUIRES_LOCAL_ID in reasons
    # Still uses conn-phys-rut's price ($8 + $2 = $10), NOT silently replaced with conn-local-esim
    assert rep_infeasible.score.total_cost_usd == Decimal(10)
    assert rep_infeasible.score.total_cost_clp == Decimal(10000)

    # Exact overpayment arithmetic on valid_expensive ($65 vs Local $12, vs Zero $65)
    rep_exp = summary.replications[3]
    assert rep_exp.score is not None
    assert rep_exp.score.is_feasible is True
    assert rep_exp.score.total_cost_usd == Decimal(65)
    assert rep_exp.score.total_cost_clp == Decimal(65000)
    assert rep_exp.score.overpayment_vs_local_usd == Decimal(53)
    assert rep_exp.score.overpayment_vs_local_clp == Decimal(53000)
    expected_pct = (Decimal(53) / Decimal(12)) * Decimal(100)
    assert rep_exp.score.overpayment_vs_local_pct == expected_pct
    assert rep_exp.score.overpayment_vs_zero_friction_usd == Decimal(0)
    assert rep_exp.score.overpayment_vs_zero_friction_clp == Decimal(0)
    assert rep_exp.score.extra_friction_vs_zero_friction == Decimal(0)

    # Exact friction arithmetic on valid_cheaper (conn-global-esim + xfer-bus)
    rep_cheap = summary.replications[4]
    assert rep_cheap.score is not None
    conn_global = repo.get_option("conn-global-esim")
    xfer_bus = repo.get_option("xfer-bus")
    assert conn_global is not None and xfer_bus is not None
    expected_friction = scenario_friction_score((conn_global, xfer_bus))
    expected_local_friction = report.local_optimized_baseline.friction_score
    assert rep_cheap.score.friction_score == expected_friction
    assert rep_cheap.score.extra_friction_vs_local == expected_friction - expected_local_friction
    assert rep_cheap.score.total_cost_usd == Decimal(42)
    assert rep_cheap.score.overpayment_vs_local_usd == Decimal(30)
    assert rep_cheap.score.overpayment_vs_zero_friction_usd == Decimal(-23)

    # Only FEASIBLE replies feed the cost aggregates (an infeasible reply would hide overcharge):
    # the infeasible -2 reply is excluded, so the mean is ( 53 + 30 ) / 2 = 41.5
    assert summary.overpayment_vs_local_usd is not None
    assert summary.overpayment_vs_local_usd.sample_size == 2
    assert summary.overpayment_vs_local_usd.mean == Decimal("41.5")
    assert summary.overpayment_vs_local_usd.lower < summary.overpayment_vs_local_usd.mean
    assert summary.overpayment_vs_local_usd.upper > summary.overpayment_vs_local_usd.mean

    # Mean friction matches expected mean across the 3 valid replies
    conn_phys = repo.get_option("conn-phys-rut")
    assert conn_phys is not None
    assert friction_score(conn_phys) > 0
    assert summary.friction_score is not None
    assert summary.friction_score.lower < summary.friction_score.mean < summary.friction_score.upper


def test_confidence_interval_95_known_cases() -> None:
    assert compute_confidence_interval_95([]) is None

    single = compute_confidence_interval_95([Decimal("12.50")])
    assert single is not None
    assert single.mean == Decimal("12.50")
    assert single.lower == Decimal("12.50")
    assert single.upper == Decimal("12.50")
    assert single.margin_of_error == Decimal(0)

    identical = compute_confidence_interval_95([Decimal(10), Decimal(10), Decimal(10)])
    assert identical is not None
    assert identical.margin_of_error == Decimal(0)
    assert identical.lower == identical.upper == Decimal(10)

    # For n=3 (df=2), values=[10, 20, 30]: mean=20, std_dev=10, SE=10/sqrt(3), t_crit=4.30265273
    ci = compute_confidence_interval_95([10, 20, 30])
    assert ci is not None
    assert ci.mean == Decimal(20)
    assert ci.sample_size == 3
    expected_margin = Decimal("4.3026527299") * (Decimal(10) / Decimal(3).sqrt())
    assert abs(ci.margin_of_error - expected_margin) < Decimal("0.0001")
    assert ci.lower == ci.mean - ci.margin_of_error
    assert ci.upper == ci.mean + ci.margin_of_error


def test_same_inputs_give_identical_text_and_json_report() -> None:
    repo = _build_synthetic_repo()
    traveler = _esim_tourist_traveler()
    reply = json.dumps({"CONNECTIVITY": "conn-global-esim", "AIRPORT_TRANSFER": "xfer-bus"})

    use_case = AuditAIAssistantsUseCase(repo)
    report_1 = use_case.execute(
        traveler,
        {"assistant-a": SequenceFakeAssistant([reply, reply, reply])},
        replications=3,
    )
    report_2 = use_case.execute(
        traveler,
        {"assistant-a": SequenceFakeAssistant([reply, reply, reply])},
        replications=3,
    )

    assert report_1.to_text() == report_2.to_text()
    assert report_1.to_json() == report_2.to_json()
    parsed_json = json.loads(report_1.to_json())
    assert parsed_json["city_id"] == "city-test"
    assert parsed_json["assistants"]["assistant-a"]["validity_rate"] == pytest.approx(1.0)
