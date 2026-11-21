"""Tests for the 'audit' CLI subcommand and existing CLI compatibility."""
from __future__ import annotations

import json
import urllib.request
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest

import travel_sim.cli as cli_module
from travel_sim.application.audit import build_audit_prompt
from travel_sim.application.ports import AssistantPort
from travel_sim.cli import main
from travel_sim.domain import (
    DeviceProfile,
    DiningPreference,
    FrictionTolerance,
    PaymentMethodPreference,
    TravelerProfile,
)
from travel_sim.infrastructure.anthropic_assistant import (
    API_KEY_ENV_VAR,
    BASE_URL_ENV_VAR,
    AnthropicAssistant,
    TransportResponse,
)
from travel_sim.infrastructure.json_repository import JsonOptionRepository
from travel_sim.infrastructure.replay_assistant import ReplayAssistant, ReplayMode

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "cities"
FAKE_CLI_SECRET = "dummy-cli-secret-token-99999"
FAKE_CLI_URL_TOKEN = "secret-cli-proxy-tok-77777"
FAKE_CLI_BASE_URL = f"https://proxy.example.test/{FAKE_CLI_URL_TOKEN}"


class _ScriptedAssistant(AssistantPort):
    """In-memory deterministic assistant used to build fixtures or test budget caps."""

    def __init__(self, replies_by_salt: dict[str, str], default_reply: str = "") -> None:
        self._replies_by_salt = dict(replies_by_salt)
        self._default_reply = default_reply
        self.calls: list[tuple[str, str]] = []

    def ask(self, prompt: str, salt: str) -> str:
        self.calls.append((prompt, salt))
        return self._replies_by_salt.get(salt, self._default_reply)


def _record_fixture(
    log_path: Path,
    *,
    assistants_replies: dict[str, list[str]],
    city_id: str = "scl",
    days: int = 7,
    data_gb: Decimal = Decimal(10),
    device: str = "esim-only",
    has_local_id: bool = False,
    tolerance: FrictionTolerance = FrictionTolerance.MEDIUM,
) -> Path:
    repo = JsonOptionRepository(DATA_DIR)
    device_map = {
        "esim-only": DeviceProfile.esim_only(),
        "physical-only": DeviceProfile.physical_sim_only(),
        "dual": DeviceProfile.dual_sim(),
    }
    traveler = TravelerProfile(
        id="traveler-default",
        destination_city_id=city_id,
        trip_duration_days=days,
        has_local_id=has_local_id,
        target_data_gb=data_gb,
        friction_tolerance=tolerance,
        device_profile=device_map[device],
        include_day_trips=True,
        dining_preference=DiningPreference.CASUAL,
        payment_method_preference=PaymentMethodPreference.INTERNATIONAL_CARD,
    )
    options = repo.list_options(city_id)
    city = repo.get_city(city_id)
    prompt = build_audit_prompt(traveler, options, city=city)

    for name, replies in assistants_replies.items():
        salts = [f"{name}:rep-{idx}" for idx in range(len(replies))]
        fake = _ScriptedAssistant(dict(zip(salts, replies, strict=True)))
        recorder = ReplayAssistant(log_path, mode=ReplayMode.RECORD, assistant=fake)
        for salt in salts:
            recorder.ask(prompt, salt)
    return log_path


def _forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _explode(*args: object, **kwargs: object) -> object:
        raise AssertionError("Real network calls are forbidden in tests")

    monkeypatch.setattr(urllib.request, "urlopen", _explode)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", _explode)


def _forbid_live_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    def _explode_init(*args: object, **kwargs: object) -> None:
        raise AssertionError("AnthropicAssistant must never be constructed in replay mode")

    monkeypatch.setattr(AnthropicAssistant, "__init__", _explode_init)
    monkeypatch.setattr(cli_module, "AnthropicAssistant", _explode_init)


def test_audit_replay_from_prerecorded_fixture_makes_zero_network_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _forbid_network(monkeypatch)
    _forbid_live_adapter(monkeypatch)

    expensive_reply = json.dumps(
        {
            "CONNECTIVITY": "scl-conn-airalo-esim-1gb",
            "AIRPORT_TRANSFER": "scl-transfer-uber-private",
            "URBAN_TRANSIT": "scl-transit-uber-daily",
            "DAY_TRIP": "scl-daytrip-tour-valpo",
            "DINING": "scl-dining-menu-ejecutivo",
        }
    )
    local_reply = json.dumps(
        {
            "CONNECTIVITY": "scl-conn-wom-plan-zero-esim",
            "AIRPORT_TRANSFER": "scl-transfer-centropuerto-bus",
            "URBAN_TRANSIT": "scl-transit-metro-bip",
            "DAY_TRIP": "scl-daytrip-bus-valpo",
            "DINING": "scl-dining-menu-del-dia",
        }
    )

    log_path = _record_fixture(
        tmp_path / "audit_fixture.jsonl",
        assistants_replies={
            "claude": [expensive_reply, expensive_reply],
            "local-bot": [local_reply, local_reply],
        },
    )

    rc = main(
        [
            "audit",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--days",
            "7",
            "--data-gb",
            "10",
            "--device",
            "esim-only",
            "--no-local-id",
            "--tolerance",
            "MEDIUM",
            "--assistant",
            "claude=claude-sonnet-4-20250514",
            "--assistant",
            "local-bot=claude-haiku-4-20250514",
            "--replications",
            "2",
            "--log",
            str(log_path),
            "--mode",
            "replay",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["city_id"] == "scl"
    assert set(payload["assistants"].keys()) == {"claude", "local-bot"}
    assert payload["assistants"]["claude"]["valid_count"] == 2
    assert payload["assistants"]["claude"]["feasible_count"] == 2
    assert payload["assistants"]["claude"]["overpayment_vs_local_usd"]["mean"] > 0.0
    assert payload["assistants"]["local-bot"]["overpayment_vs_local_usd"]["mean"] == pytest.approx(
        0.0
    )


def test_audit_output_is_identical_across_two_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _forbid_network(monkeypatch)
    _forbid_live_adapter(monkeypatch)

    reply = json.dumps(
        {
            "CONNECTIVITY": "scl-conn-airalo-esim-1gb",
            "AIRPORT_TRANSFER": "scl-transfer-uber-private",
            "URBAN_TRANSIT": "scl-transit-uber-daily",
            "DAY_TRIP": "scl-daytrip-tour-valpo",
            "DINING": "scl-dining-menu-ejecutivo",
        }
    )
    log_path = _record_fixture(
        tmp_path / "deterministic.jsonl",
        assistants_replies={"claude": [reply, reply]},
    )

    for fmt in ("text", "json"):
        argv = [
            "audit",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--days",
            "7",
            "--data-gb",
            "10",
            "--device",
            "esim-only",
            "--no-local-id",
            "--tolerance",
            "MEDIUM",
            "--assistant",
            "claude=claude-sonnet-4-20250514",
            "--replications",
            "2",
            "--log",
            str(log_path),
            "--format",
            fmt,
        ]
        rc1 = main(argv)
        cap1 = capsys.readouterr()
        rc2 = main(argv)
        cap2 = capsys.readouterr()

        assert rc1 == 0
        assert rc2 == 0
        assert cap1.out == cap2.out
        assert cap1.err == cap2.err == ""


def test_record_mode_refused_without_allow_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _forbid_network(monkeypatch)
    _forbid_live_adapter(monkeypatch)
    log_path = tmp_path / "should_not_exist.jsonl"

    rc = main(
        [
            "audit",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--assistant",
            "claude=claude-sonnet-4-20250514",
            "--replications",
            "2",
            "--log",
            str(log_path),
            "--mode",
            "record",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 2
    assert captured.out == ""
    assert "--allow-network" in captured.err
    assert "Traceback" not in captured.err
    assert not log_path.exists()


def test_record_mode_budget_cap_stops_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _forbid_network(monkeypatch)

    reply = json.dumps(
        {
            "CONNECTIVITY": "scl-conn-wom-plan-zero-esim",
            "AIRPORT_TRANSFER": "scl-transfer-centropuerto-bus",
            "URBAN_TRANSIT": "scl-transit-metro-bip",
            "DAY_TRIP": "scl-daytrip-bus-valpo",
            "DINING": "scl-dining-menu-del-dia",
        }
    )
    created: list[_ScriptedAssistant] = []

    def fake_factory(model: str) -> AssistantPort:
        del model
        bot = _ScriptedAssistant({}, default_reply=reply)
        created.append(bot)
        return bot

    log_path = tmp_path / "budget_cap.jsonl"
    rc = main(
        [
            "audit",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--assistant",
            "alpha=claude-sonnet-4-20250514",
            "--assistant",
            "beta=claude-haiku-4-20250514",
            "--replications",
            "2",
            "--log",
            str(log_path),
            "--mode",
            "record",
            "--allow-network",
            "--max-calls",
            "3",
        ],
        assistant_factory=fake_factory,
    )
    captured = capsys.readouterr()

    assert rc == 2
    assert captured.out == ""
    assert "budget" in captured.err.lower()
    assert "Traceback" not in captured.err
    assert sum(len(bot.calls) for bot in created) == 3


def test_record_mode_budget_counts_http_retries_and_redacts_secrets_in_cli_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _forbid_network(monkeypatch)
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_CLI_SECRET)
    monkeypatch.setenv(BASE_URL_ENV_VAR, FAKE_CLI_BASE_URL)

    http_attempts = 0

    def always_429_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        nonlocal http_attempts
        del url, headers, body, timeout
        http_attempts += 1
        return TransportResponse(
            status_code=429,
            body=b'{"error":{"message":"rate limited"}}',
        )

    rc_budget = main(
        [
            "audit",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--assistant",
            "alpha=claude-sonnet-4-20250514",
            "--replications",
            "2",
            "--log",
            str(tmp_path / "retry_budget.jsonl"),
            "--mode",
            "record",
            "--allow-network",
            "--max-calls",
            "2",
        ],
        assistant_factory=lambda model: AnthropicAssistant(
            model=model,
            max_retries=3,
            backoff_seconds=0.0,
            sleep=lambda _: None,
            transport=always_429_transport,
        ),
    )
    cap_budget = capsys.readouterr()
    assert rc_budget == 2
    assert http_attempts == 2
    assert "budget" in cap_budget.err.lower()

    def leaking_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        del headers, body, timeout
        return TransportResponse(
            status_code=401,
            body=json.dumps(
                {
                    "error": {
                        "type": "authentication_error",
                        "message": (
                            f"Rejected key {FAKE_CLI_SECRET} at {url} "
                            f"base={FAKE_CLI_BASE_URL} tok={FAKE_CLI_URL_TOKEN}"
                        ),
                    }
                }
            ).encode("utf-8"),
        )

    rc_leak = main(
        [
            "audit",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--assistant",
            "alpha=claude-sonnet-4-20250514",
            "--replications",
            "1",
            "--log",
            str(tmp_path / "leak_check.jsonl"),
            "--mode",
            "record",
            "--allow-network",
            "--max-calls",
            "5",
        ],
        assistant_factory=lambda model: AnthropicAssistant(
            model=model,
            transport=leaking_transport,
        ),
    )
    cap_leak = capsys.readouterr()
    assert rc_leak == 2
    assert FAKE_CLI_SECRET not in cap_leak.err
    assert FAKE_CLI_BASE_URL not in cap_leak.err
    assert FAKE_CLI_URL_TOKEN not in cap_leak.err
    assert f"/{FAKE_CLI_URL_TOKEN}" not in cap_leak.err


def test_replay_miss_and_invalid_audit_args_return_exit_code_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _forbid_network(monkeypatch)
    _forbid_live_adapter(monkeypatch)
    empty_log = tmp_path / "missing.jsonl"

    cases = [
        [
            "audit",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--assistant",
            "claude=claude-sonnet-4-20250514",
            "--log",
            str(empty_log),
        ],
        [
            "audit",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--assistant",
            "missing-equals",
            "--log",
            str(empty_log),
        ],
        [
            "audit",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--assistant",
            "dup=model-a",
            "--assistant",
            "dup=model-b",
            "--log",
            str(empty_log),
        ],
        [
            "audit",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--assistant",
            "claude=model-a",
            "--max-calls",
            "-1",
            "--log",
            str(empty_log),
        ],
    ]

    for argv in cases:
        rc = main(argv)
        captured = capsys.readouterr()
        assert rc == 2
        assert captured.err.strip() != ""
        assert "Traceback" not in captured.err


def test_existing_simulate_output_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc_text = main(
        [
            "simulate",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--days",
            "7",
            "--data-gb",
            "10",
            "--device",
            "esim-only",
            "--no-local-id",
            "--tolerance",
            "MEDIUM",
            "--format",
            "text",
        ]
    )
    cap_text = capsys.readouterr()
    assert rc_text == 0
    assert cap_text.err == ""
    assert "=== Cero Friccion ===" in cap_text.out
    assert "=== Balanceado ===" in cap_text.out
    assert "=== Optimizado Local ===" in cap_text.out

    rc_json = main(
        [
            "simulate",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--days",
            "7",
            "--data-gb",
            "10",
            "--device",
            "esim-only",
            "--no-local-id",
            "--tolerance",
            "MEDIUM",
            "--format",
            "json",
        ]
    )
    cap_json = capsys.readouterr()
    assert rc_json == 0
    assert cap_json.err == ""
    payload = json.loads(cap_json.out)
    assert payload["city"]["id"] == "scl"
    assert [s["scenario_type"] for s in payload["scenarios"]] == [
        "ZERO_FRICTION",
        "BALANCED",
        "LOCAL_OPTIMIZED",
    ]
