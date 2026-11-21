"""Local standard-library HTTP server and pure handlers for the travel simulator UI."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from travel_sim.application.ports import OptionRepository
from travel_sim.application.simulate import simulate
from travel_sim.cli import DEFAULT_DATA_DIR, simulation_to_dict
from travel_sim.domain import DeviceProfile, FrictionTolerance
from travel_sim.infrastructure.json_repository import (
    JsonOptionRepository,
    RepositoryValidationError,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
MAX_REQUEST_BODY_BYTES = 16_384
STATIC_DIR = Path(__file__).resolve().parent / "web_static"

_DEVICE_CHOICES: tuple[str, ...] = ("esim-only", "physical-only", "dual")
_REQUIRED_SIMULATE_FIELDS: tuple[str, ...] = (
    "city",
    "days",
    "data_gb",
    "device",
    "has_local_id",
    "tolerance",
)
_ALLOWED_SIMULATE_FIELDS: frozenset[str] = frozenset(_REQUIRED_SIMULATE_FIELDS)

_CONTENT_TYPES: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def _device_profile_from_choice(choice: str) -> DeviceProfile:
    if choice == "esim-only":
        return DeviceProfile.esim_only()
    if choice == "physical-only":
        return DeviceProfile.physical_sim_only()
    if choice == "dual":
        return DeviceProfile.dual_sim()
    raise ValueError(f"Unsupported device choice: {choice!r}")


def _resolve_repository(
    repository: OptionRepository | None = None,
    data_dir: str | Path = DEFAULT_DATA_DIR,
) -> OptionRepository:
    if repository is not None:
        return repository
    path = Path(data_dir)
    if not path.is_dir():
        raise NotADirectoryError(f"Data directory not found: {path}")
    return JsonOptionRepository(path)


def handle_cities(
    request: Mapping[str, Any] | None = None,
    *,
    repository: OptionRepository | None = None,
    data_dir: str | Path = DEFAULT_DATA_DIR,
) -> tuple[int, dict[str, Any]]:
    """Pure handler for GET /api/cities returning (status_code, payload_dict)."""
    if request is not None and not isinstance(request, Mapping):
        return 400, {"error": "Invalid request: expected a mapping object."}

    try:
        repo = _resolve_repository(repository=repository, data_dir=data_dir)
        cities = sorted(repo.list_cities(), key=lambda c: c.id)
        return 200, {
            "cities": [
                {
                    "id": city.id,
                    "name": city.name,
                    "country_code": city.country_code,
                    "local_currency": city.local_currency,
                    "unverified": not city.is_verified,
                }
                for city in cities
            ]
        }
    except (
        FileNotFoundError,
        NotADirectoryError,
        RepositoryValidationError,
        OSError,
    ) as exc:
        return 500, {"error": f"Failed to load city catalog: {exc}"}
    except Exception:  # noqa: BLE001 (HTTP boundary: never leak tracebacks)
        return 500, {"error": "Internal server error while listing cities."}


def handle_simulate(
    payload: Any,
    *,
    repository: OptionRepository | None = None,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    reference_time: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Pure handler for POST /api/simulate taking a dict and returning (status, dict)."""
    if not isinstance(payload, Mapping):
        return 400, {"error": "Invalid request payload: expected a JSON object."}

    unknown_fields = sorted(
        str(key) for key in payload if key not in _ALLOWED_SIMULATE_FIELDS
    )
    if unknown_fields:
        joined = ", ".join(unknown_fields)
        return 400, {
            "error": f"Unknown field(s) in request: {joined}.",
            "field": unknown_fields[0],
        }

    for field_name in _REQUIRED_SIMULATE_FIELDS:
        if field_name not in payload or payload[field_name] is None:
            return 400, {
                "error": f"Missing required field '{field_name}'.",
                "field": field_name,
            }

    raw_city = payload["city"]
    if not isinstance(raw_city, str) or not raw_city.strip():
        return 400, {
            "error": "Invalid 'city': must be a non-empty string.",
            "field": "city",
        }
    city_id = raw_city.strip()

    raw_days = payload["days"]
    if isinstance(raw_days, bool) or not isinstance(raw_days, int) or raw_days < 1:
        return 400, {
            "error": "Invalid 'days': must be an integer >= 1.",
            "field": "days",
        }
    days = raw_days

    raw_data_gb = payload["data_gb"]
    if isinstance(raw_data_gb, bool) or not isinstance(
        raw_data_gb, (int, float, Decimal, str)
    ):
        return 400, {
            "error": "Invalid 'data_gb': must be a non-negative finite number.",
            "field": "data_gb",
        }
    if isinstance(raw_data_gb, str) and not raw_data_gb.strip():
        return 400, {
            "error": "Invalid 'data_gb': must be a non-negative finite number.",
            "field": "data_gb",
        }
    try:
        data_gb = Decimal(str(raw_data_gb))
    except (InvalidOperation, ValueError):
        return 400, {
            "error": "Invalid 'data_gb': must be a non-negative finite number.",
            "field": "data_gb",
        }
    if not data_gb.is_finite() or data_gb < 0:
        return 400, {
            "error": "Invalid 'data_gb': must be a non-negative finite number.",
            "field": "data_gb",
        }

    raw_device = payload["device"]
    if not isinstance(raw_device, str) or raw_device not in _DEVICE_CHOICES:
        allowed_devices = ", ".join(_DEVICE_CHOICES)
        return 400, {
            "error": f"Invalid 'device': must be one of {allowed_devices}.",
            "field": "device",
        }
    device_choice = raw_device

    raw_has_local_id = payload["has_local_id"]
    if not isinstance(raw_has_local_id, bool):
        return 400, {
            "error": "Invalid 'has_local_id': must be a boolean.",
            "field": "has_local_id",
        }
    has_local_id = raw_has_local_id

    raw_tolerance = payload["tolerance"]
    if not isinstance(raw_tolerance, str) or not raw_tolerance.strip():
        allowed_tol = ", ".join(member.value for member in FrictionTolerance)
        return 400, {
            "error": f"Invalid 'tolerance': must be one of {allowed_tol}.",
            "field": "tolerance",
        }
    try:
        tolerance = FrictionTolerance(raw_tolerance.strip().upper())
    except ValueError:
        allowed_tol = ", ".join(member.value for member in FrictionTolerance)
        return 400, {
            "error": f"Invalid 'tolerance': must be one of {allowed_tol}.",
            "field": "tolerance",
        }

    try:
        repo = _resolve_repository(repository=repository, data_dir=data_dir)
    except (
        FileNotFoundError,
        NotADirectoryError,
        RepositoryValidationError,
        OSError,
    ) as exc:
        return 500, {"error": f"Failed to load city catalog: {exc}"}
    except Exception:  # noqa: BLE001 (HTTP boundary: never leak tracebacks)
        return 500, {"error": "Internal server error while loading catalog."}

    if repo.get_city(city_id) is None:
        available = sorted(c.id for c in repo.list_cities())
        avail_text = ", ".join(available) if available else "none"
        return 400, {
            "error": f"Invalid 'city': unknown city '{city_id}'. Available: {avail_text}.",
            "field": "city",
        }

    if reference_time is not None:
        ref_time = reference_time
    elif clock is not None:
        ref_time = clock()
    else:
        ref_time = datetime.now(UTC)

    try:
        device_profile = _device_profile_from_choice(device_choice)
        result = simulate(
            repo,
            city_id=city_id,
            device_profile=device_profile,
            trip_duration_days=days,
            has_local_id=has_local_id,
            target_data_gb=data_gb,
            friction_tolerance=tolerance,
            reference_time=ref_time,
        )
        return 200, simulation_to_dict(result, device_choice=device_choice)
    except (ValueError, TypeError) as exc:
        return 400, {"error": f"Invalid simulation parameters: {exc}"}
    except Exception:  # noqa: BLE001 (HTTP boundary: never leak tracebacks)
        return 500, {"error": "Internal server error during simulation."}


def handle_simulate_bytes(
    raw_body: bytes,
    *,
    max_body_bytes: int = MAX_REQUEST_BODY_BYTES,
    repository: OptionRepository | None = None,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    reference_time: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Validate raw request body length and JSON syntax before delegating to handle_simulate."""
    if len(raw_body) > max_body_bytes:
        return 400, {
            "error": f"Request body exceeds limit of {max_body_bytes} bytes.",
        }
    if not raw_body or not raw_body.strip():
        return 400, {"error": "Request body must not be empty."}
    try:
        decoded = raw_body.decode("utf-8")
        payload = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"error": "Malformed JSON in request body."}

    return handle_simulate(
        payload,
        repository=repository,
        data_dir=data_dir,
        reference_time=reference_time,
        clock=clock,
    )


def resolve_static_file(
    request_path: str,
    *,
    static_dir: Path = STATIC_DIR,
) -> Path | None:
    """Safely resolve a URL path inside static_dir, preventing path traversal."""
    if not isinstance(request_path, str) or "\x00" in request_path or "\\" in request_path:
        return None

    parsed_path = unquote(urlsplit(request_path).path)
    if "\x00" in parsed_path or "\\" in parsed_path:
        return None

    if parsed_path in ("", "/"):
        rel_name = "index.html"
    elif parsed_path.startswith("/static/"):
        rel_name = parsed_path.removeprefix("/static/")
    elif parsed_path.startswith("/"):
        rel_name = parsed_path.lstrip("/")
    else:
        return None

    if not rel_name:
        rel_name = "index.html"

    parts = Path(rel_name).parts
    if not parts:
        return None
    for part in parts:
        if part in ("", ".", "..") or part.startswith("."):
            return None

    base_dir = static_dir.resolve()
    candidate = (base_dir / rel_name).resolve()
    if not candidate.is_relative_to(base_dir):
        return None
    if not candidate.is_file():
        return None
    return candidate


def handle_static(
    request_path: str,
    *,
    static_dir: Path = STATIC_DIR,
) -> tuple[int, bytes, str]:
    """Pure static file handler returning (status_code, content_bytes, content_type)."""
    target = resolve_static_file(request_path, static_dir=static_dir)
    if target is None:
        body = json.dumps({"error": "Not found."}).encode("utf-8")
        return 404, body, "application/json; charset=utf-8"

    content_type = _CONTENT_TYPES.get(
        target.suffix.lower(),
        "application/octet-stream",
    )
    return 200, target.read_bytes(), content_type


class TravelSimRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler serving static UI assets and JSON simulation endpoints."""

    repository: OptionRepository | None = None
    data_dir: str | Path = DEFAULT_DATA_DIR
    static_dir: Path = STATIC_DIR
    max_body_bytes: int = MAX_REQUEST_BODY_BYTES
    reference_time: datetime | None = None
    clock: Callable[[], datetime] | None = None

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress noisy default stderr logging during requests."""
        del format, args

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        content_type: str,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: Mapping[str, Any]) -> None:
        body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        """Handle GET requests for /api/cities and static files."""
        try:
            clean_path = urlsplit(self.path).path
            if clean_path == "/api/cities":
                status, payload = handle_cities(
                    {},
                    repository=self.repository,
                    data_dir=self.data_dir,
                )
                self._send_json(status, payload)
                return

            if clean_path.startswith("/api/"):
                self._send_json(404, {"error": "API endpoint not found."})
                return

            status, body, content_type = handle_static(
                self.path,
                static_dir=self.static_dir,
            )
            self._send_bytes(status, body, content_type)
        except Exception:  # noqa: BLE001 (HTTP boundary: never leak tracebacks)
            self._send_json(500, {"error": "Internal server error."})

    def do_POST(self) -> None:
        """Handle POST requests for /api/simulate with strict body size and JSON checks."""
        try:
            clean_path = urlsplit(self.path).path
            if clean_path != "/api/simulate":
                self._send_json(404, {"error": "API endpoint not found."})
                return

            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                self._send_json(400, {"error": "Missing Content-Length header."})
                return
            try:
                content_length = int(raw_length)
            except ValueError:
                self._send_json(400, {"error": "Invalid Content-Length header."})
                return

            if content_length < 0:
                self._send_json(400, {"error": "Invalid Content-Length header."})
                return
            if content_length > self.max_body_bytes:
                self._send_json(
                    400,
                    {
                        "error": (
                            f"Request body exceeds limit of {self.max_body_bytes} bytes."
                        )
                    },
                )
                return

            raw_body = self.rfile.read(content_length)
            status, payload = handle_simulate_bytes(
                raw_body,
                max_body_bytes=self.max_body_bytes,
                repository=self.repository,
                data_dir=self.data_dir,
                reference_time=self.reference_time,
                clock=self.clock,
            )
            self._send_json(status, payload)
        except Exception:  # noqa: BLE001 (HTTP boundary: never leak tracebacks)
            self._send_json(500, {"error": "Internal server error."})


def create_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    repository: OptionRepository | None = None,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    static_dir: Path = STATIC_DIR,
    max_body_bytes: int = MAX_REQUEST_BODY_BYTES,
    reference_time: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ThreadingHTTPServer:
    """Create a configured ThreadingHTTPServer bound to (host, port)."""
    repo = _resolve_repository(repository=repository, data_dir=data_dir)

    class ConfiguredHandler(TravelSimRequestHandler):
        pass

    ConfiguredHandler.repository = repo
    ConfiguredHandler.data_dir = data_dir
    ConfiguredHandler.static_dir = static_dir
    ConfiguredHandler.max_body_bytes = max_body_bytes
    ConfiguredHandler.reference_time = reference_time
    ConfiguredHandler.clock = clock

    return ThreadingHTTPServer((host, port), ConfiguredHandler)


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for python -m travel_sim.web."""
    parser = argparse.ArgumentParser(
        prog="python -m travel_sim.web",
        description="Local web server for the travel cost-vs-friction simulator.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Bind address (default: {DEFAULT_HOST}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Bind TCP port (default: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        help=f"Directory containing city JSON files (default: {DEFAULT_DATA_DIR}).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entrypoint for starting the local travel simulator web UI."""
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    if not (0 <= args.port <= 65535):
        sys.stderr.write(f"Error: --port must be between 0 and 65535, got {args.port}\n")
        return 2

    try:
        server = create_server(
            host=args.host,
            port=args.port,
            data_dir=args.data_dir,
        )
    except (
        FileNotFoundError,
        NotADirectoryError,
        RepositoryValidationError,
        OSError,
    ) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 2

    bound_host, bound_port = server.server_address[:2]
    sys.stdout.write(
        f"Viaje Real web UI listening on {bound_host}:{bound_port}\n"
    )
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "MAX_REQUEST_BODY_BYTES",
    "STATIC_DIR",
    "TravelSimRequestHandler",
    "build_parser",
    "create_server",
    "handle_cities",
    "handle_simulate",
    "handle_simulate_bytes",
    "handle_static",
    "main",
    "resolve_static_file",
]


if __name__ == "__main__":
    raise SystemExit(main())
