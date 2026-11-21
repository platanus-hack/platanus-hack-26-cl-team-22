"""Unit and integration tests for travel_sim.web pure handlers and static UI assets."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from travel_sim.application.simulate import simulate
from travel_sim.cli import DEFAULT_DATA_DIR, simulation_to_dict
from travel_sim.domain import DeviceProfile, FrictionTolerance
from travel_sim.infrastructure.json_repository import JsonOptionRepository
from travel_sim.web import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    MAX_REQUEST_BODY_BYTES,
    STATIC_DIR,
    build_parser,
    handle_cities,
    handle_simulate,
    handle_simulate_bytes,
    handle_static,
    resolve_static_file,
)

FIXED_REF_TIME = datetime(2026, 11, 25, 12, 0, 0, tzinfo=UTC)


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "city": "scl",
        "days": 7,
        "data_gb": 10,
        "device": "dual",
        "has_local_id": False,
        "tolerance": "MEDIUM",
    }
    base.update(overrides)
    return base


def test_handle_cities_returns_expected_structure() -> None:
    status, data = handle_cities({})
    assert status == 200
    assert "cities" in data
    assert isinstance(data["cities"], list)
    assert len(data["cities"]) >= 1

    santiago = next((c for c in data["cities"] if c["id"] == "scl"), None)
    assert santiago is not None
    assert santiago["name"] == "Santiago"
    assert santiago["country_code"] == "CL"
    assert santiago["local_currency"] == "CLP"
    assert isinstance(santiago["unverified"], bool)


def test_handle_simulate_returns_expected_cli_json_structure() -> None:
    payload = _valid_payload()
    status, data = handle_simulate(payload, reference_time=FIXED_REF_TIME)
    assert status == 200

    repo = JsonOptionRepository(DEFAULT_DATA_DIR)
    expected_result = simulate(
        repo,
        city_id="scl",
        device_profile=DeviceProfile.dual_sim(),
        trip_duration_days=7,
        has_local_id=False,
        target_data_gb=Decimal(10),
        friction_tolerance=FrictionTolerance.MEDIUM,
        reference_time=FIXED_REF_TIME,
    )
    expected_dict = simulation_to_dict(expected_result, device_choice="dual")
    assert data == expected_dict

    assert data["city"]["id"] == "scl"
    assert data["traveler"]["trip_duration_days"] == 7
    assert len(data["scenarios"]) == 3
    labels = [s["label"] for s in data["scenarios"]]
    assert labels == ["Cero Friccion", "Balanceado", "Optimizado Local"]

    for scenario in data["scenarios"]:
        assert "total_cost_usd" in scenario
        assert "total_cost_clp" in scenario
        assert "savings_vs_zero_friction" in scenario
        assert "friction_score" in scenario
        assert "extra_time_minutes" in scenario
        assert "choices" in scenario
        assert "unverified" in scenario

    assert "missing_categories" in data
    assert "rejected_options" in data
    assert "unverified" in data
    assert "unverified_option_ids" in data


@pytest.mark.parametrize(
    "bad_payload",
    [
        None,
        [],
        "not-a-dict",
        {},
        _valid_payload(city=""),
        _valid_payload(city="   "),
        _valid_payload(city=123),
        _valid_payload(city="unknown-city-xyz"),
        _valid_payload(days=0),
        _valid_payload(days=-5),
        _valid_payload(days=True),
        _valid_payload(days=3.5),
        _valid_payload(days="7"),
        _valid_payload(data_gb=-1),
        _valid_payload(data_gb="not-a-number"),
        _valid_payload(data_gb="NaN"),
        _valid_payload(data_gb="Infinity"),
        _valid_payload(data_gb=True),
        _valid_payload(device="invalid-device"),
        _valid_payload(device=""),
        _valid_payload(device=42),
        _valid_payload(has_local_id="false"),
        _valid_payload(has_local_id=0),
        _valid_payload(has_local_id=None),
        _valid_payload(tolerance="EXTREME"),
        _valid_payload(tolerance=""),
        _valid_payload(tolerance=50),
        _valid_payload(extra_unexpected_field="boom"),
    ],
)
def test_handle_simulate_invalid_input_returns_400_without_traceback(
    bad_payload: Any,
) -> None:
    status, data = handle_simulate(bad_payload, reference_time=FIXED_REF_TIME)
    assert status == 400
    assert isinstance(data, dict)
    assert "error" in data
    assert isinstance(data["error"], str)
    assert len(data["error"].strip()) > 0
    serialized = json.dumps(data)
    assert "Traceback" not in serialized
    assert "File \"" not in serialized


def test_handle_simulate_missing_each_required_field_returns_400() -> None:
    for required_field in (
        "city",
        "days",
        "data_gb",
        "device",
        "has_local_id",
        "tolerance",
    ):
        payload = _valid_payload()
        del payload[required_field]
        status, data = handle_simulate(payload, reference_time=FIXED_REF_TIME)
        assert status == 400
        assert "error" in data
        assert required_field in data["error"]
        assert "Traceback" not in json.dumps(data)


def test_handle_simulate_bytes_enforces_body_size_limit_and_valid_json() -> None:
    oversized = b"{" + b" " * (MAX_REQUEST_BODY_BYTES + 10) + b"}"
    status, data = handle_simulate_bytes(oversized)
    assert status == 400
    assert "error" in data
    assert "Traceback" not in json.dumps(data)

    status_empty, data_empty = handle_simulate_bytes(b"   ")
    assert status_empty == 400
    assert "error" in data_empty

    status_bad_json, data_bad_json = handle_simulate_bytes(b"{not valid json")
    assert status_bad_json == 400
    assert "error" in data_bad_json
    assert "Traceback" not in json.dumps(data_bad_json)


def test_esim_only_device_never_selects_physical_sim_option() -> None:
    payload = _valid_payload(device="esim-only", data_gb=10)
    status, data = handle_simulate(payload, reference_time=FIXED_REF_TIME)
    assert status == 200

    for scenario in data["scenarios"]:
        for choice in scenario["choices"]:
            assert choice["sim_type"] != "PHYSICAL_SIM", (
                f"Scenario {scenario['scenario_type']} selected physical SIM "
                f"{choice['option_id']} for esim-only device"
            )

    rejected_physical = [
        item
        for item in data["rejected_options"]
        if item["sim_type"] == "PHYSICAL_SIM"
    ]
    assert len(rejected_physical) >= 1
    for item in rejected_physical:
        assert "UNSUPPORTED_PHYSICAL_SIM" in item["reasons"]


def test_output_identical_across_two_calls() -> None:
    payload = _valid_payload(device="esim-only", days=10, data_gb=15)
    status_first, data_first = handle_simulate(payload)
    status_second, data_second = handle_simulate(payload)

    assert status_first == 200
    assert status_second == 200
    assert data_first == data_second
    assert json.dumps(data_first, sort_keys=True) == json.dumps(
        data_second, sort_keys=True
    )


def test_static_files_exist_and_serve_properly() -> None:
    expected_files = ("index.html", "app.js", "style.css")
    for filename in expected_files:
        file_path = STATIC_DIR / filename
        assert file_path.is_file(), f"Missing static file: {file_path}"
        assert file_path.stat().st_size > 0

    status_root, body_root, ctype_root = handle_static("/")
    assert status_root == 200
    assert "text/html" in ctype_root
    assert b"Viaje Real" in body_root

    status_js, body_js, ctype_js = handle_static("/app.js")
    assert status_js == 200
    assert "javascript" in ctype_js
    assert b"/api/simulate" in body_js

    status_css, body_css, ctype_css = handle_static("/style.css")
    assert status_css == 200
    assert "text/css" in ctype_css
    assert b"prefers-color-scheme: dark" in body_css


@pytest.mark.parametrize(
    "malicious_path",
    [
        "/../cli.py",
        "/../../pyproject.toml",
        "/..%2fcli.py",
        "/static/../../travel_sim/web.py",
        "/%2e%2e/%2e%2e/README.md",
        "/\\..\\cli.py",
        "/index.html\x00.txt",
        "/.hidden",
    ],
)
def test_static_handler_never_serves_files_outside_static_dir(
    malicious_path: str,
) -> None:
    assert resolve_static_file(malicious_path) is None
    status, body, _ = handle_static(malicious_path)
    assert status == 404
    assert b"def " not in body


def test_static_files_contain_no_external_urls_and_no_innerhtml() -> None:
    for filename in ("index.html", "app.js", "style.css"):
        content = (STATIC_DIR / filename).read_text(encoding="utf-8")
        assert "http://" not in content, f"Found http:// in {filename}"
        assert "https://" not in content, f"Found https:// in {filename}"
        assert "innerHTML" not in content, f"Found innerHTML in {filename}"
        assert "outerHTML" not in content, f"Found outerHTML in {filename}"
        assert "insertAdjacentHTML" not in content, (
            f"Found insertAdjacentHTML in {filename}"
        )
        assert "eval(" not in content, f"Found eval( in {filename}"


def test_cli_parser_defaults_to_localhost() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    assert args.host == DEFAULT_HOST == "127.0.0.1"
    assert args.port == DEFAULT_PORT == 8000

    custom_args = parser.parse_args(["--host", "127.0.0.1", "--port", "9090"])
    assert custom_args.host == "127.0.0.1"
    assert custom_args.port == 9090
