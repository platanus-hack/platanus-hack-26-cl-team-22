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

from travel_sim.application.audit import run_audit
from travel_sim.application.ports import AssistantPort
from travel_sim.application.scenarios import TripScenario
from travel_sim.application.simulate import SimulationResult, simulate
from travel_sim.domain import (
    DeviceProfile,
    DiningPreference,
    FreshnessStatus,
    FrictionTolerance,
    PaymentMethodPreference,
    ScenarioType,
    TravelerProfile,
)
from travel_sim.infrastructure.anthropic_assistant import (
    AnthropicAssistant,
    AnthropicAssistantError,
)
from travel_sim.infrastructure.json_repository import (
    JsonOptionRepository,
    RepositoryValidationError,
)
from travel_sim.infrastructure.replay_assistant import (
    BudgetExceededError,
    ReplayAssistant,
    ReplayMissError,
    ReplayMode,
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


def _parse_non_negative_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected an integer, got {raw!r}") from exc
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {value}")
    return value


def _parse_assistant_spec(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(
            f"invalid --assistant specification {raw!r}; expected NAME=MODEL"
        )
    name, model = raw.split("=", 1)
    name = name.strip()
    model = model.strip()
    if not name or not model:
        raise argparse.ArgumentTypeError(
            f"invalid --assistant specification {raw!r}; both NAME and MODEL must be non-empty"
        )
    return name, model


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


def _add_common_trip_args(subparser: argparse.ArgumentParser, *, city_help: str) -> None:
    subparser.add_argument(
        "--city",
        required=True,
        metavar="ID",
        help=city_help,
    )
    subparser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        metavar="DIR",
        help=f"Directory containing city JSON files (default: {DEFAULT_DATA_DIR}).",
    )
    subparser.add_argument(
        "--days",
        type=_parse_positive_int,
        default=7,
        metavar="INT",
        help="Trip duration in days (default: 7).",
    )
    subparser.add_argument(
        "--data-gb",
        type=_parse_non_negative_decimal,
        default=Decimal(0),
        metavar="NUMBER",
        help="Target mobile data usage in GB (default: 0).",
    )
    subparser.add_argument(
        "--device",
        choices=_DEVICE_CHOICES,
        default="dual",
        help="Traveler device SIM capability (default: dual).",
    )

    local_id_group = subparser.add_mutually_exclusive_group()
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
    subparser.set_defaults(has_local_id=False)

    tolerance_choices = ",".join(member.value for member in FrictionTolerance)
    subparser.add_argument(
        "--tolerance",
        type=_parse_tolerance,
        default=FrictionTolerance.MEDIUM,
        metavar=f"{{{tolerance_choices}}}",
        help=f"Friction tolerance level ({tolerance_choices}; default: MEDIUM).",
    )
    subparser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )


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
    _add_common_trip_args(sim_parser, city_help="City identifier to simulate (e.g., scl).")
    sim_parser.add_argument(
        "--reference-time",
        default=None,
        metavar="ISO8601",
        help="Reference UTC timestamp for freshness checks (ISO 8601; defaults to clock).",
    )

    audit_parser = subparsers.add_parser(
        "audit",
        help="Audit AI assistant recommendations against deterministic baselines.",
    )
    _add_common_trip_args(audit_parser, city_help="City identifier to audit (e.g., scl).")
    audit_parser.add_argument(
        "--assistant",
        dest="assistants",
        action="append",
        type=_parse_assistant_spec,
        required=True,
        metavar="NAME=MODEL",
        help="Assistant specification NAME=MODEL (repeatable).",
    )
    audit_parser.add_argument(
        "--replications",
        type=_parse_positive_int,
        default=5,
        metavar="N",
        help="Number of salted replications per assistant (default: 5).",
    )
    audit_parser.add_argument(
        "--log",
        required=True,
        metavar="PATH",
        help="JSONL record/replay log file path.",
    )
    audit_parser.add_argument(
        "--mode",
        choices=("replay", "record"),
        default="replay",
        help="Operating mode: replay from JSONL log or record live calls (default: replay).",
    )
    audit_parser.add_argument(
        "--allow-network",
        action="store_true",
        default=False,
        help="Permit live network calls (required for --mode record).",
    )
    audit_parser.add_argument(
        "--max-calls",
        type=_parse_non_negative_int,
        default=50,
        metavar="N",
        help="Maximum live assistant API calls allowed in record mode (default: 50).",
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


def _load_validated_city(data_dir: str, raw_city: str) -> tuple[str, JsonOptionRepository] | None:
    city_id = raw_city.strip()
    if not city_id:
        sys.stderr.write("Error: --city must be a non-empty city identifier.\n")
        return None

    repository = _load_repository(data_dir)
    if repository.get_city(city_id) is None:
        available = sorted(city.id for city in repository.list_cities())
        avail_text = ", ".join(available) if available else "(none)"
        sys.stderr.write(
            f"Error: unknown city '{city_id}'. Available cities: {avail_text}\n"
        )
        return None
    return city_id, repository


def _handle_simulate(
    args: argparse.Namespace,
    *,
    clock: Callable[[], datetime] | None = None,
) -> int:
    loaded = _load_validated_city(args.data_dir, args.city)
    if loaded is None:
        return 2
    city_id, repository = loaded

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


class _SharedCallBudget:
    """Tracks live assistant call budget across all assistants in one audit run."""

    def __init__(self, max_calls: int) -> None:
        self.max_calls = max_calls
        self.calls_made = 0

    def consume(self, salt: str) -> None:
        if self.calls_made >= self.max_calls:
            raise BudgetExceededError(
                f"Call budget cap of {self.max_calls} reached; refusing call for salt={salt!r}"
            )
        self.calls_made += 1


class _BudgetedAssistant(AssistantPort):
    """AssistantPort wrapper enforcing a shared live call budget."""

    def __init__(self, inner: AssistantPort, budget: _SharedCallBudget) -> None:
        self._inner = inner
        self._budget = budget

    def ask(self, prompt: str, salt: str) -> str:
        self._budget.consume(salt)
        return self._inner.ask(prompt, salt)


def _handle_audit(
    args: argparse.Namespace,
    *,
    assistant_factory: Callable[[str], AssistantPort] | None = None,
) -> int:
    mode = ReplayMode(args.mode)
    if mode == ReplayMode.RECORD and not args.allow_network:
        sys.stderr.write(
            "Error: record mode requires --allow-network to permit live assistant API calls.\n"
        )
        return 2

    assistant_specs: list[tuple[str, str]] = list(args.assistants)
    seen_names: set[str] = set()
    for name, _model in assistant_specs:
        if name in seen_names:
            raise ValueError(f"Duplicate --assistant name: {name!r}")
        seen_names.add(name)

    loaded = _load_validated_city(args.data_dir, args.city)
    if loaded is None:
        return 2
    city_id, repository = loaded

    traveler = TravelerProfile(
        id="traveler-default",
        destination_city_id=city_id,
        trip_duration_days=args.days,
        has_local_id=args.has_local_id,
        target_data_gb=args.data_gb,
        friction_tolerance=args.tolerance,
        device_profile=_device_profile_from_choice(args.device),
        include_day_trips=True,
        dining_preference=DiningPreference.CASUAL,
        payment_method_preference=PaymentMethodPreference.INTERNATIONAL_CARD,
    )

    log_path = Path(args.log)
    shared_budget = _SharedCallBudget(args.max_calls)
    assistants: dict[str, AssistantPort] = {}
    for name, model in assistant_specs:
        if mode == ReplayMode.REPLAY:
            assistants[name] = ReplayAssistant(
                log_path,
                mode=ReplayMode.REPLAY,
                assistant=None,
                max_calls=args.max_calls,
            )
        else:
            live_assistant = (
                assistant_factory(model)
                if assistant_factory is not None
                else AnthropicAssistant(model=model)
            )
            assistants[name] = ReplayAssistant(
                log_path,
                mode=ReplayMode.RECORD,
                assistant=_BudgetedAssistant(live_assistant, shared_budget),
                max_calls=args.max_calls,
            )

    report = run_audit(
        repository,
        traveler,
        assistants,
        replications=args.replications,
    )
    if args.format == "json":
        sys.stdout.write(report.to_json() + "\n")
    else:
        sys.stdout.write(report.to_text() + "\n")
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    assistant_factory: Callable[[str], AssistantPort] | None = None,
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
        if args.command == "audit":
            return _handle_audit(args, assistant_factory=assistant_factory)
        sys.stderr.write(f"Error: unknown command {args.command!r}\n")
        return 2
    except ReplayMissError as exc:
        detail = exc.args[0] if exc.args else str(exc)
        sys.stderr.write(f"Error: {detail}\n")
        return 2
    except (
        AnthropicAssistantError,
        BudgetExceededError,
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
