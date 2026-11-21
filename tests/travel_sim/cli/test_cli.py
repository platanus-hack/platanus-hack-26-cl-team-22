"""Tests for the travel_sim command-line interface."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from travel_sim.cli import main

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "cities"


def test_simulate_text_format_renders_three_scenarios_and_metrics(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
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
            "dual",
            "--no-local-id",
            "--tolerance",
            "MEDIUM",
            "--format",
            "text",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    out = captured.out
    assert "=== Cero Friccion ===" in out
    assert "=== Balanceado ===" in out
    assert "=== Optimizado Local ===" in out
    assert "USD" in out
    assert "CLP" in out
    assert "Savings vs Cero Friccion:" in out
    assert "Friction score:" in out
    assert "Extra minutes:" in out
    assert "=== Rejected Options ===" in out


def test_simulate_json_format_is_machine_readable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        [
            "simulate",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
            "--days",
            "5",
            "--data-gb",
            "15",
            "--device",
            "dual",
            "--has-local-id",
            "--tolerance",
            "HIGH",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    payload = json.loads(captured.out)

    assert payload["city"]["id"] == "scl"
    assert payload["traveler"]["trip_duration_days"] == 5
    assert payload["traveler"]["target_data_gb"] == 15.0
    assert payload["traveler"]["has_local_id"] is True
    assert payload["traveler"]["friction_tolerance"] == "HIGH"
    assert [s["scenario_type"] for s in payload["scenarios"]] == [
        "ZERO_FRICTION",
        "BALANCED",
        "LOCAL_OPTIMIZED",
    ]
    assert [s["label"] for s in payload["scenarios"]] == [
        "Cero Friccion",
        "Balanceado",
        "Optimizado Local",
    ]
    for scenario in payload["scenarios"]:
        assert "total_cost_usd" in scenario
        assert "total_cost_clp" in scenario
        assert "friction_score" in scenario
        assert "extra_time_minutes" in scenario
        assert "savings_vs_zero_friction" in scenario
        assert len(scenario["choices"]) > 0


def test_esim_only_device_never_shows_physical_sim_in_scenarios(
    capsys: pytest.CaptureFixture[str],
) -> None:
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
            "--format",
            "json",
        ]
    )
    cap_json = capsys.readouterr()
    assert rc_json == 0
    payload = json.loads(cap_json.out)

    for scenario in payload["scenarios"]:
        for choice in scenario["choices"]:
            assert choice["sim_type"] != "PHYSICAL_SIM"
            assert "chip-fisico" not in choice["option_id"]

    rejected_by_id = {item["option_id"]: item for item in payload["rejected_options"]}
    assert "scl-conn-wom-chip-fisico" in rejected_by_id
    assert "UNSUPPORTED_PHYSICAL_SIM" in rejected_by_id["scl-conn-wom-chip-fisico"]["reasons"]
    assert "scl-conn-entel-chip-fisico" in rejected_by_id
    assert "UNSUPPORTED_PHYSICAL_SIM" in rejected_by_id["scl-conn-entel-chip-fisico"]["reasons"]

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
            "--format",
            "text",
        ]
    )
    cap_text = capsys.readouterr()
    assert rc_text == 0
    scenarios_section, rejected_section = cap_text.out.split("=== Rejected Options ===", maxsplit=1)
    assert "scl-conn-wom-chip-fisico" not in scenarios_section
    assert "scl-conn-entel-chip-fisico" not in scenarios_section
    assert "UNSUPPORTED_PHYSICAL_SIM" in rejected_section


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["simulate"],
        ["simulate", "--city", "scl", "--days", "0"],
        ["simulate", "--city", "scl", "--days", "-3"],
        ["simulate", "--city", "scl", "--days", "not-an-int"],
        ["simulate", "--city", "scl", "--data-gb", "-1"],
        ["simulate", "--city", "scl", "--data-gb", "nan"],
        ["simulate", "--city", "scl", "--device", "satellite"],
        ["simulate", "--city", "scl", "--tolerance", "EXTREME"],
        ["simulate", "--city", "scl", "--format", "xml"],
        ["simulate", "--city", "scl", "--has-local-id", "--no-local-id"],
        ["simulate", "--city", "scl", "--unknown-flag"],
        ["simulate", "--city", "scl", "--data-dir", "/nonexistent/path/for/travel_sim"],
    ],
)
def test_invalid_arguments_exit_with_code_2_and_no_traceback(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(argv)
    captured = capsys.readouterr()

    assert rc == 2
    assert captured.err.strip() != ""
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_unknown_city_returns_clear_error(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(
        [
            "simulate",
            "--city",
            "atlantis",
            "--data-dir",
            str(DATA_DIR),
        ]
    )
    captured = capsys.readouterr()

    assert rc == 2
    assert captured.out == ""
    assert "atlantis" in captured.err
    assert "scl" in captured.err
    assert "Traceback" not in captured.err


def test_unverified_banner_appears_with_santiago_seed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        [
            "simulate",
            "--city",
            "scl",
            "--data-dir",
            str(DATA_DIR),
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0
    lines = captured.out.splitlines()
    # Unverified options are excluded by default and the CLI says so.
    assert lines[0].startswith("NOTE [UNVERIFIED DATA EXCLUDED]")
    assert "--include-unverified" in lines[0]
    warning = next(line for line in lines if line.startswith("WARNING [UNVERIFIED DATA]"))
    assert "last_verified_at" in warning


def test_include_unverified_flag_opts_in_and_changes_the_totals(
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = ["simulate", "--city", "scl", "--data-dir", str(DATA_DIR), "--days", "5",
            "--data-gb", "20", "--format", "json"]
    assert main(base) == 0
    strict = json.loads(capsys.readouterr().out)
    assert main([*base, "--include-unverified"]) == 0
    loose = json.loads(capsys.readouterr().out)

    assert strict["include_unverified"] is False
    assert loose["include_unverified"] is True


def test_output_is_identical_across_two_runs(capsys: pytest.CaptureFixture[str]) -> None:
    for fmt in ("text", "json"):
        argv = [
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
            "--tolerance",
            "low",
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


def test_cities_subcommand_lists_available_city_ids(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["cities", "--data-dir", str(DATA_DIR)])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    assert captured.out.splitlines() == ["scl"]
