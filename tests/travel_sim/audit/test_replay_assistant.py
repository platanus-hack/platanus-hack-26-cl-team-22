"""Tests for the JSONL ReplayAssistant adapter."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from travel_sim.application.audit import run_audit
from travel_sim.application.ports import AssistantPort
from travel_sim.domain import (
    DeviceProfile,
    DiningPreference,
    FrictionTolerance,
    PaymentMethodPreference,
    TravelerProfile,
)
from travel_sim.infrastructure.json_repository import JsonOptionRepository
from travel_sim.infrastructure.replay_assistant import (
    BudgetExceededError,
    ReplayAssistant,
    ReplayMissError,
    ReplayMode,
    compute_cache_key,
)


class CountingFakeAssistant:
    """Deterministic fake assistant keyed by salt that counts invocations."""

    def __init__(self, replies_by_salt: dict[str, str], default_reply: str = "") -> None:
        self._replies_by_salt = dict(replies_by_salt)
        self._default_reply = default_reply
        self.call_count = 0

    def ask(self, prompt: str, salt: str) -> str:
        del prompt
        self.call_count += 1
        return self._replies_by_salt.get(salt, self._default_reply)


class ExplodingAssistant:
    """Spy assistant that must never be invoked during replay."""

    def __init__(self) -> None:
        self.call_count = 0

    def ask(self, prompt: str, salt: str) -> str:
        self.call_count += 1
        raise AssertionError(f"Unexpected live call in replay mode: salt={salt!r}")


def _build_repo() -> JsonOptionRepository:
    payload = {
        "city": {
            "id": "city-replay",
            "name": "Replay City",
            "country_code": "CL",
            "local_currency": "CLP",
            "default_usd_exchange_rate": 1000.0,
            "last_verified_at": "2026-11-01T00:00:00Z",
        },
        "options": [
            {
                "id": "conn-local",
                "city_id": "city-replay",
                "category": "CONNECTIVITY",
                "provider": "Local",
                "name": "Local eSIM",
                "cost_local_currency": 10000,
                "cost_usd_reference": 10,
                "pricing_model": "ONE_TIME_PACKAGE",
                "validity_days": 30,
                "data_quota_gb": 50.0,
                "setup_time_minutes": 20,
                "paperwork_level": 1,
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
                "id": "conn-global",
                "city_id": "city-replay",
                "category": "CONNECTIVITY",
                "provider": "Global",
                "name": "Global eSIM",
                "cost_local_currency": 20000,
                "cost_usd_reference": 20,
                "pricing_model": "ONE_TIME_PACKAGE",
                "validity_days": 7,
                "data_quota_gb": 10.0,
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
        ],
    }
    repo = JsonOptionRepository()
    repo.load_dict(payload, source="<replay-synthetic>")
    return repo


def _traveler() -> TravelerProfile:
    return TravelerProfile(
        id="t-replay",
        destination_city_id="city-replay",
        trip_duration_days=7,
        has_local_id=False,
        target_data_gb=Decimal(5),
        friction_tolerance=FrictionTolerance.MEDIUM,
        device_profile=DeviceProfile.esim_only(),
        include_day_trips=False,
        dining_preference=DiningPreference.CASUAL,
        payment_method_preference=PaymentMethodPreference.INTERNATIONAL_CARD,
    )


def test_cache_key_hashes_salt_and_prompt_without_boundary_collision() -> None:
    k1 = compute_cache_key("bc", "a")
    k2 = compute_cache_key("c", "ab")
    assert len(k1) == 64
    assert k1 != k2
    assert k1 == compute_cache_key("bc", "a")


def test_record_then_replay_gives_identical_results_with_zero_calls(tmp_path: Path) -> None:
    repo = _build_repo()
    traveler = _traveler()
    fixture_path = tmp_path / "recordings" / "audit.jsonl"

    salts = ("s-0", "s-1", "s-2")
    fake = CountingFakeAssistant(
        {
            "s-0": json.dumps({"CONNECTIVITY": "conn-global"}),
            "s-1": "not-json-garbage",
            "s-2": json.dumps({"CONNECTIVITY": "conn-local"}),
        }
    )

    recorder = ReplayAssistant(
        fixture_path,
        mode=ReplayMode.RECORD,
        assistant=fake,
        max_calls=3,
    )
    assert isinstance(recorder, AssistantPort)

    recorded_report = run_audit(
        repo,
        traveler,
        {"bot": recorder},
        replications=3,
        salts_by_assistant={"bot": salts},
    )
    assert fake.call_count == 3
    assert recorder.calls_made == 3
    assert fixture_path.is_file()
    lines = [line for line in fixture_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 3

    spy = ExplodingAssistant()
    replayer = ReplayAssistant(fixture_path, mode=ReplayMode.REPLAY, assistant=spy)
    replayed_report = run_audit(
        repo,
        traveler,
        {"bot": replayer},
        replications=3,
        salts_by_assistant={"bot": salts},
    )

    assert spy.call_count == 0
    assert replayer.calls_made == 0
    assert replayer.replay_hits == 3
    assert replayed_report.to_json() == recorded_report.to_json()
    assert replayed_report.to_text() == recorded_report.to_text()


def test_replay_mode_raises_on_missing_key_and_makes_zero_calls(tmp_path: Path) -> None:
    fixture_path = tmp_path / "empty.jsonl"
    spy = ExplodingAssistant()
    replayer = ReplayAssistant(fixture_path, mode="replay", assistant=spy)

    with pytest.raises(ReplayMissError):
        replayer.ask("prompt-1", "salt-1")

    assert spy.call_count == 0
    assert replayer.calls_made == 0


def test_budget_cap_stops_audit_run(tmp_path: Path) -> None:
    repo = _build_repo()
    traveler = _traveler()
    fixture_path = tmp_path / "budget.jsonl"

    fake = CountingFakeAssistant(
        {},
        default_reply=json.dumps({"CONNECTIVITY": "conn-global"}),
    )
    capped = ReplayAssistant(
        fixture_path,
        mode="record",
        assistant=fake,
        max_calls=2,
    )

    with pytest.raises(BudgetExceededError):
        run_audit(repo, traveler, {"bot": capped}, replications=4)

    assert fake.call_count == 2
    assert capped.calls_made == 2
