"""Command-line interface for the deterministic travel cost-vs-friction simulator."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from travel_sim.application.scenarios import TripScenario
from travel_sim.application.simulate import SimulationResult, simulate
from travel_sim.domain import DeviceProfile, FreshnessStatus, FrictionTolerance, ScenarioType
from travel_sim.infrastructure.json_repository import (
    JsonOptionRepository,
    RepositoryValidationError,
)

DEFAULT_DATA_DIR = "data/cities"

_SCENARIO_ORDER: tuple[ScenarioType, ...] = (
    ScenarioType.ZERO_FRICTION,
    ScenarioType.BALANCED,
    ScenarioType.LOCAL_OPTIMIZED,
)

_SCENARIO_LABELS: dict[ScenarioType, str] = {
    ScenarioType.ZERO_FRICTION: "Cero Friccion",
    ScenarioType.BALANCED: "Balanceado",
    ScenarioType.LOCAL_OPTIMIZED: "Optimizado Local",
}

_DEVICE_CHOICES: tuple[str, ...] = ("esim-only", "physical-only", "dual")


def _device_profile_from_choice(choice: str) -> DeviceProfile:
    if choice == "esim-only":
        return DeviceProfile.esim_only()
    if choice == "physical-only":
        return DeviceProfile.physical_sim_only()
    if choice == "dual":
        return DeviceProfile.dual_sim()
    raise ValueError(f"Unsupported device choice: {choice!r}")


def _parse_positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected an integer, got {raw!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {value}")
    return value


def _parse_non_negative_decimal(raw: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"expected a number, got {raw!r}") from exc
    if not value.is_finite() or value < 0:
        raise argparse.ArgumentTypeError(f"must be a non-negative finite number, got {raw!r}")
    return value


def _parse_tolerance(raw: str) -> FrictionTolerance:
    normalized = raw.strip().upper()
    try:
        return FrictionTolerance(normalized)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in FrictionTolerance)
        raise argparse.ArgumentTypeError(
            f"invalid tolerance {raw!r}; choose from: {allowed}"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse CLI parser."""
    parser = argparse.ArgumentParser(
        prog="travel-sim",
        description="Deterministic travel cost-vs-friction simulator.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sim_parser = subparsers.add_parser(
        "simulate",
        help="Run a travel simulation and display the three scenarios.",
    )
    sim_parser.add_argument(
        "--city",
        required=True,
        metavar="ID",
        help="City identifier to simulate (e.g., scl).",
    )
    sim_parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        metavar="DIR",
        help=f"Directory containing city JSON files (default: {DEFAULT_DATA_DIR}).",
    )
    sim_parser.add_argument(
        "--days",
        type=_parse_positive_int,
        default=7,
        metavar="INT",
        help="Trip duration in days (default: 7).",
    )
    sim_parser.add_argument(
        "--data-gb",
        type=_parse_non_negative_decimal,
        default=Decimal(0),
        metavar="NUMBER",
        help="Target mobile data usage in GB (default: 0).",
    )
    sim_parser.add_argument(
        "--device",
        choices=_DEVICE_CHOICES,
        default="dual",
        help="Traveler device SIM capability (default: dual).",
    )

    local_id_group = sim_parser.add_mutually_exclusive_group()
    local_id_group.add_argument(
        "--has-local-id",
        dest="has_local_id",
        action="store_true",
        help="Traveler holds a local national ID.",
    )
    local_id_group.add_argument(
        "--no-local-id",
        dest="has_local_id",
        action="store_false",
        help="Traveler does not hold a local national ID (default).",
    )
    sim_parser.set_defaults(has_local_id=False)

    tolerance_choices = ",".join(member.value for member in FrictionTolerance)
    sim_parser.add_argument(
        "--tolerance",
        type=_parse_tolerance,
        default=FrictionTolerance.MEDIUM,
        metavar=f"{{{tolerance_choices}}}",
        help=f"Friction tolerance level ({tolerance_choices}; default: MEDIUM).",
    )
    sim_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    sim_parser.add_argument(
        "--reference-time",
        default=None,
        metavar="ISO8601",
        help="Reference UTC timestamp for freshness checks (ISO 8601; defaults to clock).",
    )

    cities_parser = subparsers.add_parser(
        "cities",
        help="List available city identifiers.",
    )
    cities_parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        metavar="DIR",
        help=f"Directory containing city JSON files (default: {DEFAULT_DATA_DIR}).",
    )

    return parser


def _format_usd(amount: Decimal) -> str:
    return f"${amount:,.2f}"


def _format_local(amount: Decimal, currency: str) -> str:
    if amount == amount.to_integral_value():
        return f"{amount:,.0f} {currency}"
    return f"{amount:,.2f} {currency}"


def _format_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    header_line = " | ".join(h.ljust(widths[idx]) for idx, h in enumerate(headers))
    separator = "-+-".join("-" * width for width in widths)
    lines = [header_line, separator]
    for row in rows:
        lines.append(" | ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row)))
    return lines


def format_simulation_text(result: SimulationResult, *, device_choice: str) -> str:
    """Format a SimulationResult as readable per-scenario tables."""
    lines: list[str] = []
    warning_lines: list[str] = []

    if result.unverified:
        unverified_count = len(result.unverified_option_ids)
        if result.city_unverified and unverified_count == 0:
            warning_lines.append(
                "WARNING [UNVERIFIED DATA]: city metadata lacks a verification timestamp "
                "(last_verified_at is null)."
            )
        elif result.city_unverified:
            warning_lines.append(
                "WARNING [UNVERIFIED DATA]: "
                f"city metadata and {unverified_count} option(s) in this catalog are "
                "unverified (missing last_verified_at or verification_source_url)."
            )
        else:
            warning_lines.append(
                "WARNING [UNVERIFIED DATA]: "
                f"{unverified_count} option(s) in this catalog are unverified "
                "(missing last_verified_at or verification_source_url)."
            )

    city_expired = result.city_freshness == FreshnessStatus.EXPIRED
    if city_expired or result.expired_option_ids:
        parts: list[str] = []
        if city_expired:
            parts.append("city metadata")
        if result.expired_option_ids:
            ids_text = ", ".join(result.expired_option_ids)
            parts.append(f"{len(result.expired_option_ids)} option(s) ({ids_text})")
        warning_lines.append(
            f"WARNING [EXPIRED DATA]: {' and '.join(parts)} exceeded the 180-day "
            "freshness window (re-verification required)."
        )

    city_stale = result.city_freshness == FreshnessStatus.STALE
    if city_stale or result.stale_option_ids:
        parts = []
        if city_stale:
            parts.append("city metadata")
        if result.stale_option_ids:
            ids_text = ", ".join(result.stale_option_ids)
            parts.append(f"{len(result.stale_option_ids)} option(s) ({ids_text})")
        warning_lines.append(
            f"WARNING [STALE DATA]: {' and '.join(parts)} are in the 61-180 day "
            "stale freshness window."
        )

    if warning_lines:
        lines.extend(warning_lines)
        lines.append("")

    city_name = result.city.name if result.city is not None else result.city_id
    currency = result.city.local_currency if result.city is not None else "CLP"
    tolerance_val = (
        result.traveler.friction_tolerance.value
        if isinstance(result.traveler.friction_tolerance, FrictionTolerance)
        else str(result.traveler.friction_tolerance)
    )
    lines.append(
        f"City: {city_name} ({result.city_id}) | Days: {result.traveler.trip_duration_days} | "
        f"Data: {result.traveler.target_data_gb} GB | Device: {device_choice} | "
        f"Local ID: {'yes' if result.traveler.has_local_id else 'no'} | "
        f"Tolerance: {tolerance_val}"
    )
    if result.missing_categories:
        missing_text = ", ".join(cat.value for cat in result.missing_categories)
        lines.append(f"Missing categories: {missing_text}")

    for scenario_type in _SCENARIO_ORDER:
        scenario = result.scenarios[scenario_type]
        label = _SCENARIO_LABELS[scenario_type]
        lines.append("")
        lines.append(f"=== {label} ===")

        headers = ("Category", "Option", "Option ID", "USD", currency, "Friction", "Extra min")
        rows: list[tuple[str, str, str, str, str, str, str]] = []
        for category in result.categories:
            choice = scenario.choice_for(category)
            if choice is None:
                rows.append((category.value, "(no compatible option)", "-", "-", "-", "-", "-"))
            else:
                rows.append(
                    (
                        category.value,
                        choice.option.name,
                        choice.option.id,
                        _format_usd(choice.total_cost_usd),
                        _format_local(choice.total_cost_clp, currency),
                        f"{choice.friction_score:.2f}",
                        f"{choice.extra_time_minutes}",
                    )
                )
        lines.extend(_format_table(headers, rows))

        savings = scenario.savings
        lines.append(
            f"Total: {_format_usd(scenario.total_cost_usd)} USD / "
            f"{_format_local(scenario.total_cost_clp, currency)}"
        )
        lines.append(
            f"Savings vs Cero Friccion: {_format_usd(savings.savings_usd)} USD / "
            f"{_format_local(savings.savings_clp, currency)} "
            f"({savings.savings_percentage:.1f}%)"
        )
        lines.append(
            f"Friction score: {scenario.friction_score:.2f} | "
            f"Extra minutes: {scenario.extra_time_minutes} min"
        )

    lines.append("")
    lines.append("=== Rejected Options ===")
    if result.rejected_options:
        rej_headers = ("Category", "Option", "Option ID", "Reasons")
        rej_rows = [
            (
                item.option.category.value,
                item.option.name,
                item.option.id,
                ", ".join(reason.value for reason in item.reasons),
            )
            for item in result.rejected_options
        ]
        lines.extend(_format_table(rej_headers, rej_rows))
    else:
        lines.append("None")

    return "\n".join(lines) + "\n"


def _scenario_to_dict(scenario: TripScenario) -> dict[str, Any]:
    choices_list: list[dict[str, Any]] = []
    for choice in scenario.choices:
        choices_list.append(
            {
                "category": choice.category.value,
                "option_id": choice.option.id,
                "name": choice.option.name,
                "provider": choice.option.provider,
                "sim_type": choice.option.sim_type.value,
                "total_cost_usd": float(choice.total_cost_usd),
                "total_cost_local": float(choice.total_cost_local),
                "total_cost_clp": float(choice.total_cost_clp),
                "daily_cost_usd": float(choice.daily_cost_usd),
                "friction_score": float(choice.friction_score),
                "setup_time_minutes": choice.setup_time_minutes,
                "extra_time_minutes": choice.extra_time_minutes,
                "savings_usd": float(choice.savings_usd),
                "savings_clp": float(choice.savings_clp),
                "unverified": choice.unverified,
            }
        )

    savings = scenario.savings
    return {
        "scenario_type": scenario.scenario_type.value,
        "label": _SCENARIO_LABELS[scenario.scenario_type],
        "total_cost_usd": float(scenario.total_cost_usd),
        "total_cost_local": float(scenario.total_cost_local),
        "total_cost_clp": float(scenario.total_cost_clp),
        "daily_cost_usd": float(scenario.daily_cost_usd),
        "daily_cost_clp": float(scenario.daily_cost_clp),
        "friction_score": float(scenario.friction_score),
        "total_friction_score": float(scenario.total_friction_score),
        "total_setup_time_minutes": scenario.total_setup_time_minutes,
        "extra_time_minutes": scenario.extra_time_minutes,
        "savings_vs_zero_friction": {
            "savings_usd": float(savings.savings_usd),
            "savings_local": float(savings.savings_local),
            "savings_clp": float(savings.savings_clp),
            "savings_percentage": float(savings.savings_percentage),
            "friction_delta": float(savings.friction_delta),
            "extra_time_minutes": savings.extra_time_minutes,
        },
        "missing_categories": [cat.value for cat in scenario.missing_categories],
        "unverified": scenario.unverified,
        "unverified_option_ids": list(scenario.unverified_option_ids),
        "choices": choices_list,
    }


def simulation_to_dict(result: SimulationResult, *, device_choice: str) -> dict[str, Any]:
    """Convert a SimulationResult into a stable, JSON-serializable dictionary."""
    tolerance_val: str | float = (
        result.traveler.friction_tolerance.value
        if isinstance(result.traveler.friction_tolerance, FrictionTolerance)
        else float(result.traveler.friction_tolerance)
    )
    city_info: dict[str, Any] = {
        "id": result.city_id,
        "name": result.city.name if result.city is not None else result.city_id,
        "country_code": result.city.country_code if result.city is not None else None,
        "local_currency": result.city.local_currency if result.city is not None else "CLP",
        "unverified": result.city_unverified,
        "freshness_status": (
            result.city_freshness.value if result.city_freshness is not None else None
        ),
    }
    return {
        "city": city_info,
        "traveler": {
            "trip_duration_days": result.traveler.trip_duration_days,
            "target_data_gb": float(result.traveler.target_data_gb),
            "has_local_id": result.traveler.has_local_id,
            "friction_tolerance": tolerance_val,
            "device_profile": {
                "mode": device_choice,
                "supports_physical_sim": result.device_profile.supports_physical_sim,
                "supports_esim": result.device_profile.supports_esim,
            },
        },
        "unverified": result.unverified,
        "unverified_option_ids": list(result.unverified_option_ids),
        "stale_option_ids": list(result.stale_option_ids),
        "expired_option_ids": list(result.expired_option_ids),
        "option_freshness": {
            opt_id: status.value for opt_id, status in result.option_freshness.items()
        },
        "categories": [cat.value for cat in result.categories],
        "missing_categories": [cat.value for cat in result.missing_categories],
        "scenarios": [_scenario_to_dict(result.scenarios[s]) for s in _SCENARIO_ORDER],
        "rejected_options": [
            {
                "option_id": item.option.id,
                "category": item.option.category.value,
                "name": item.option.name,
                "provider": item.option.provider,
                "sim_type": item.option.sim_type.value,
                "reasons": [reason.value for reason in item.reasons],
            }
            for item in result.rejected_options
        ],
    }


def format_simulation_json(result: SimulationResult, *, device_choice: str) -> str:
    """Format a SimulationResult as stable, indented JSON."""
    payload = simulation_to_dict(result, device_choice=device_choice)
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _load_repository(data_dir: str) -> JsonOptionRepository:
    path = Path(data_dir)
    if not path.is_dir():
        raise NotADirectoryError(f"Data directory not found: {path}")
    return JsonOptionRepository(path)


def _handle_cities(args: argparse.Namespace) -> int:
    repository = _load_repository(args.data_dir)
    city_ids = sorted(city.id for city in repository.list_cities())
    if city_ids:
        sys.stdout.write("\n".join(city_ids) + "\n")
    return 0


def _handle_simulate(
    args: argparse.Namespace,
    *,
    clock: Callable[[], datetime] | None = None,
) -> int:
    city_id = args.city.strip()
    if not city_id:
        sys.stderr.write("Error: --city must be a non-empty city identifier.\n")
        return 2

    repository = _load_repository(args.data_dir)
    if repository.get_city(city_id) is None:
        available = sorted(city.id for city in repository.list_cities())
        avail_text = ", ".join(available) if available else "(none)"
        sys.stderr.write(
            f"Error: unknown city '{city_id}'. Available cities: {avail_text}\n"
        )
        return 2

    if args.reference_time is not None:
        ref_time = datetime.fromisoformat(args.reference_time)
    elif clock is not None:
        ref_time = clock()
    else:
        ref_time = datetime.now(UTC)

    device_profile = _device_profile_from_choice(args.device)
    result = simulate(
        repository,
        city_id=city_id,
        device_profile=device_profile,
        trip_duration_days=args.days,
        has_local_id=args.has_local_id,
        target_data_gb=args.data_gb,
        friction_tolerance=args.tolerance,
        reference_time=ref_time,
    )

    if args.format == "json":
        sys.stdout.write(format_simulation_json(result, device_choice=args.device))
    else:
        sys.stdout.write(format_simulation_text(result, device_choice=args.device))
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
) -> int:
    """CLI entrypoint returning process exit code (0 on success, 2 on invalid input)."""
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    try:
        if args.command == "cities":
            return _handle_cities(args)
        if args.command == "simulate":
            return _handle_simulate(args, clock=clock)
        sys.stderr.write(f"Error: unknown command {args.command!r}\n")
        return 2
    except (
        FileNotFoundError,
        NotADirectoryError,
        RepositoryValidationError,
        ValueError,
        OSError,
    ) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 2


__all__ = [
    "DEFAULT_DATA_DIR",
    "build_parser",
    "format_simulation_json",
    "format_simulation_text",
    "main",
    "simulation_to_dict",
]
