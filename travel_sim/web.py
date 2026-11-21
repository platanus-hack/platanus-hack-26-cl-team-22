"""Local standard-library HTTP server and pure handlers for the travel simulator UI."""
from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import math
import socket
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from http import HTTPStatus
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

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_REQUEST_TIMEOUT = 10.0
MAX_REQUEST_BODY_BYTES = 16_384
MIN_DAYS = 1
MAX_DAYS = 365
MIN_DATA_GB = Decimal(0)
MAX_DATA_GB = Decimal(1000)
STATIC_DIR = Path(__file__).resolve().parent / "web_static"

_HTML_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)
_ALLOWED_HOSTNAMES: frozenset[str] = frozenset({"localhost", "127.0.0.1", "[::1]"})

_DEVICE_CHOICES: tuple[str, ...] = ("esim-only", "physical-only", "dual")
_REQUIRED_SIMULATE_FIELDS: tuple[str, ...] = (
    "city",
    "days",
    "data_gb",
    "device",
    "has_local_id",
    "tolerance",
)
_OPTIONAL_SIMULATE_FIELDS: tuple[str, ...] = ("reference_time",)
_ALLOWED_SIMULATE_FIELDS: frozenset[str] = frozenset(
    _REQUIRED_SIMULATE_FIELDS + _OPTIONAL_SIMULATE_FIELDS
)

_CONTENT_TYPES: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class _LocalThreadingHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server configured with daemon worker threads."""

    daemon_threads = True
    allow_reuse_address = True


def is_loopback_host(host: str) -> bool:
    """Return True when host names a loopback address (127.0.0.1, ::1, localhost)."""
    if not isinstance(host, str):
        return False
    normalized = host.strip().lower()
    if not normalized:
        return False
    if normalized == "localhost":
        return True
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _invalid_field(field: str, message: str) -> tuple[int, dict[str, Any]]:
    return 400, {"error": message, "field": field}


def _reject_non_finite_json_constant(token: str) -> Any:
    raise ValueError(f"Non-finite JSON constant {token!r} is not allowed.")


def _parse_host_header(raw_host: str) -> tuple[str, int | None] | None:
    """Validate and parse a Host header against allowed loopback hostnames."""
    value = raw_host.strip()
    if not value or any(ord(ch) <= 0x20 or ch in "@/?#\\" for ch in value):
        return None

    if value.startswith("["):
        bracket_end = value.find("]")
        if bracket_end == -1:
            return None
        host_part = value[: bracket_end + 1].lower()
        rest = value[bracket_end + 1 :]
        if host_part != "[::1]":
            return None
        if not rest:
            return host_part, None
        if not rest.startswith(":"):
            return None
        port_str = rest[1:]
    elif ":" in value:
        if value.count(":") != 1:
            return None
        host_raw, port_str = value.split(":", 1)
        host_part = host_raw.lower()
    else:
        host_part = value.lower()
        port_str = ""

    if host_part not in _ALLOWED_HOSTNAMES:
        return None

    if ":" in value and not port_str:
        return None
    if port_str:
        if not port_str.isascii() or not port_str.isdigit():
            return None
        port = int(port_str)
        if not (1 <= port <= 65535):
            return None
        return host_part, port

    return host_part, None


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
    ):
        logger.exception("Failed to load city catalog while listing cities.")
        return 500, {"error": "Failed to load city catalog."}
    except Exception:
        logger.exception("Internal server error while listing cities.")
        return 500, {"error": "Internal server error while listing cities."}


def _parse_reference_time(
    raw_ref_time: Any,
) -> tuple[datetime | None, tuple[int, dict[str, Any]] | None]:
    if not isinstance(raw_ref_time, str) or not raw_ref_time.strip():
        return None, _invalid_field(
            "reference_time",
            "Invalid 'reference_time': must be an ISO 8601 datetime with timezone.",
        )
    try:
        parsed_ref = datetime.fromisoformat(raw_ref_time.strip())
    except ValueError:
        return None, _invalid_field(
            "reference_time",
            "Invalid 'reference_time': must be an ISO 8601 datetime with timezone.",
        )
    if parsed_ref.tzinfo is None or parsed_ref.utcoffset() is None:
        return None, _invalid_field(
            "reference_time",
            "Invalid 'reference_time': must be an ISO 8601 datetime with timezone.",
        )
    return parsed_ref, None


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
        return _invalid_field("city", "Invalid 'city': must be a non-empty string.")
    city_id = raw_city.strip()

    raw_days = payload["days"]
    if (
        isinstance(raw_days, bool)
        or not isinstance(raw_days, int)
        or raw_days < MIN_DAYS
        or raw_days > MAX_DAYS
    ):
        return _invalid_field(
            "days",
            f"Invalid 'days': must be an integer between {MIN_DAYS} and {MAX_DAYS}.",
        )
    days = raw_days

    raw_data_gb = payload["data_gb"]
    data_gb_msg = (
        f"Invalid 'data_gb': must be a finite number between {MIN_DATA_GB} and {MAX_DATA_GB}."
    )
    if isinstance(raw_data_gb, bool) or not isinstance(
        raw_data_gb, (int, float, Decimal, str)
    ):
        return _invalid_field("data_gb", data_gb_msg)
    if isinstance(raw_data_gb, float) and not math.isfinite(raw_data_gb):
        return _invalid_field("data_gb", data_gb_msg)
    if isinstance(raw_data_gb, str):
        stripped_gb = raw_data_gb.strip()
        if not stripped_gb or "_" in stripped_gb:
            return _invalid_field("data_gb", data_gb_msg)
        raw_data_gb_str = stripped_gb
    else:
        raw_data_gb_str = str(raw_data_gb)
    try:
        data_gb = Decimal(raw_data_gb_str)
    except (InvalidOperation, ValueError):
        return _invalid_field("data_gb", data_gb_msg)
    if not data_gb.is_finite() or data_gb < MIN_DATA_GB or data_gb > MAX_DATA_GB:
        return _invalid_field("data_gb", data_gb_msg)

    raw_device = payload["device"]
    if not isinstance(raw_device, str) or raw_device not in _DEVICE_CHOICES:
        allowed_devices = ", ".join(_DEVICE_CHOICES)
        return _invalid_field(
            "device",
            f"Invalid 'device': must be one of {allowed_devices}.",
        )
    device_choice = raw_device

    raw_has_local_id = payload["has_local_id"]
    if not isinstance(raw_has_local_id, bool):
        return _invalid_field(
            "has_local_id",
            "Invalid 'has_local_id': must be a boolean.",
        )
    has_local_id = raw_has_local_id

    raw_tolerance = payload["tolerance"]
    allowed_tol = ", ".join(member.value for member in FrictionTolerance)
    if not isinstance(raw_tolerance, str) or not raw_tolerance.strip():
        return _invalid_field(
            "tolerance",
            f"Invalid 'tolerance': must be one of {allowed_tol}.",
        )
    try:
        tolerance = FrictionTolerance(raw_tolerance.strip().upper())
    except ValueError:
        return _invalid_field(
            "tolerance",
            f"Invalid 'tolerance': must be one of {allowed_tol}.",
        )

    payload_ref_time: datetime | None = None
    if "reference_time" in payload and payload["reference_time"] is not None:
        payload_ref_time, ref_err = _parse_reference_time(payload["reference_time"])
        if ref_err is not None:
            return ref_err

    try:
        repo = _resolve_repository(repository=repository, data_dir=data_dir)
        city = repo.get_city(city_id)
        if city is None:
            available = sorted(c.id for c in repo.list_cities())
            avail_text = ", ".join(available) if available else "none"
            return _invalid_field(
                "city",
                f"Invalid 'city': unknown city '{city_id}'. Available: {avail_text}.",
            )
    except (
        FileNotFoundError,
        NotADirectoryError,
        RepositoryValidationError,
        OSError,
    ):
        logger.exception("Failed to load city catalog during simulation.")
        return 500, {"error": "Failed to load city catalog."}
    except Exception:
        logger.exception("Internal server error while loading catalog.")
        return 500, {"error": "Internal server error while loading catalog."}

    if payload_ref_time is not None:
        ref_time = payload_ref_time
    elif reference_time is not None:
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
    except (ValueError, TypeError):
        logger.warning("Simulation rejected due to parameter validation error.", exc_info=True)
        return 400, {"error": "Invalid simulation parameters."}
    except Exception:
        logger.exception("Internal server error during simulation.")
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
        payload = json.loads(decoded, parse_constant=_reject_non_finite_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
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

    split = urlsplit(request_path)
    if split.scheme or split.netloc:
        return None

    raw_path = split.path
    if "//" in raw_path:
        return None

    parsed_path = unquote(raw_path)
    if "\x00" in parsed_path or "\\" in parsed_path or "//" in parsed_path:
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
        body = (json.dumps({"error": "Not found."}, allow_nan=False) + "\n").encode("utf-8")
        return 404, body, "application/json; charset=utf-8"

    content_type = _CONTENT_TYPES.get(
        target.suffix.lower(),
        "application/octet-stream",
    )
    return 200, target.read_bytes(), content_type


class TravelSimRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler serving static UI assets and JSON simulation endpoints."""

    server_version = "ViajeReal"
    sys_version = ""
    timeout = DEFAULT_REQUEST_TIMEOUT

    repository: OptionRepository | None = None
    data_dir: str | Path = DEFAULT_DATA_DIR
    static_dir: Path = STATIC_DIR
    max_body_bytes: int = MAX_REQUEST_BODY_BYTES
    reference_time: datetime | None = None
    clock: Callable[[], datetime] | None = None

    def version_string(self) -> str:
        """Return minimal Server header without Python or BaseHTTP version strings."""
        return self.server_version

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress noisy default stderr logging during requests."""
        del format, args

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        content_type: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type == "text/html":
            self.send_header("Content-Security-Policy", _HTML_CSP)
        if extra_headers:
            for header_name, header_value in extra_headers.items():
                self.send_header(header_name, header_value)
        self.end_headers()
        if getattr(self, "command", None) != "HEAD":
            self.wfile.write(body)

    def _send_json(
        self,
        status: int,
        payload: Mapping[str, Any],
        *,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        try:
            serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        except (ValueError, TypeError):
            logger.exception("Failed to serialize JSON response with allow_nan=False.")
            status = 500
            extra_headers = None
            serialized = json.dumps(
                {"error": "Internal server error."},
                ensure_ascii=False,
                allow_nan=False,
            )
        body = (serialized + "\n").encode("utf-8")
        self._send_bytes(
            status,
            body,
            "application/json; charset=utf-8",
            extra_headers=extra_headers,
        )

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        """Send a generic JSON error response with security headers instead of stdlib HTML."""
        del message, explain
        try:
            phrase = HTTPStatus(code).phrase
        except ValueError:
            phrase = "HTTP Error"
        if getattr(self, "request_version", "HTTP/0.9") == "HTTP/0.9":
            self.request_version = "HTTP/1.0"
        self.close_connection = True
        self._send_json(code, {"error": phrase})

    def _validate_origin_header(self, expected_host: str) -> bool:
        origins = self.headers.get_all("Origin") or []
        if not origins:
            return True
        if len(origins) > 1:
            return False
        raw_origin = origins[0].strip()
        if not raw_origin or raw_origin.lower() == "null":
            return False

        parsed = urlsplit(raw_origin)
        if parsed.scheme.lower() != "http":
            return False
        if parsed.path or parsed.query or parsed.fragment:
            return False
        if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
            return False

        parsed_origin_host = _parse_host_header(parsed.netloc)
        if parsed_origin_host is None:
            return False
        origin_host, origin_port = parsed_origin_host
        if origin_host != expected_host:
            return False

        server_port = int(self.server.server_address[1])
        effective_origin_port = 80 if origin_port is None else origin_port
        return effective_origin_port == server_port

    def _has_valid_json_content_type(self) -> bool:
        ct_values = self.headers.get_all("Content-Type") or []
        if len(ct_values) != 1:
            return False
        media_type = ct_values[0].split(";", 1)[0].strip().lower()
        return media_type == "application/json"

    def _parse_content_length(self) -> tuple[int | None, tuple[int, str] | None]:
        if self.headers.get_all("Transfer-Encoding"):
            return None, (400, "Transfer-Encoding is not supported.")

        lengths = self.headers.get_all("Content-Length") or []
        if not lengths:
            return None, (411, "Missing Content-Length header.")
        if len(lengths) > 1:
            return None, (400, "Duplicate Content-Length headers are not allowed.")

        raw_cl = lengths[0].strip()
        if not raw_cl or not raw_cl.isascii() or not raw_cl.isdigit():
            return None, (400, "Invalid Content-Length header.")

        content_length = int(raw_cl)
        if content_length > self.max_body_bytes:
            return None, (
                400,
                f"Request body exceeds limit of {self.max_body_bytes} bytes.",
            )
        return content_length, None

    def _handle_get(self, clean_path: str) -> None:
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

    def _handle_post_simulate(self) -> None:
        if not self._has_valid_json_content_type():
            self.close_connection = True
            self._send_json(
                415,
                {"error": "Unsupported Media Type: Content-Type must be application/json."},
            )
            return

        content_length, length_err = self._parse_content_length()
        if length_err is not None or content_length is None:
            err_status, err_msg = length_err or (400, "Invalid Content-Length header.")
            self.close_connection = True
            self._send_json(err_status, {"error": err_msg})
            return

        try:
            raw_body = self.rfile.read(content_length)
        except TimeoutError:
            logger.warning("Timed out waiting for POST request body.")
            self.close_connection = True
            try:
                self._send_json(408, {"error": "Request body read timed out."})
            except OSError:
                pass
            return

        if len(raw_body) != content_length:
            self.close_connection = True
            self._send_json(400, {"error": "Incomplete request body."})
            return

        status, payload = handle_simulate_bytes(
            raw_body,
            max_body_bytes=self.max_body_bytes,
            repository=self.repository,
            data_dir=self.data_dir,
            reference_time=self.reference_time,
            clock=self.clock,
        )
        self._send_json(status, payload)

    def _dispatch_request(self) -> None:
        try:
            host_headers = self.headers.get_all("Host") or []
            if len(host_headers) != 1:
                self.close_connection = True
                self._send_json(403, {"error": "Forbidden: invalid Host header."})
                return
            parsed_host = _parse_host_header(host_headers[0])
            if parsed_host is None:
                self.close_connection = True
                self._send_json(403, {"error": "Forbidden: invalid Host header."})
                return
            host_name, _host_port = parsed_host

            method = self.command
            if method == "POST" and not self._validate_origin_header(host_name):
                self.close_connection = True
                self._send_json(403, {"error": "Forbidden: invalid Origin header."})
                return

            clean_path = urlsplit(self.path).path

            if clean_path == "/api/cities":
                if method == "GET":
                    self._handle_get(clean_path)
                else:
                    self.close_connection = True
                    self._send_json(
                        405,
                        {"error": "Method not allowed."},
                        extra_headers={"Allow": "GET"},
                    )
                return

            if clean_path == "/api/simulate":
                if method == "POST":
                    self._handle_post_simulate()
                else:
                    self.close_connection = True
                    self._send_json(
                        405,
                        {"error": "Method not allowed."},
                        extra_headers={"Allow": "POST"},
                    )
                return

            if clean_path.startswith("/api/"):
                if method in ("GET", "POST"):
                    self.close_connection = True
                    self._send_json(404, {"error": "API endpoint not found."})
                else:
                    self.close_connection = True
                    self._send_json(
                        405,
                        {"error": "Method not allowed."},
                        extra_headers={"Allow": "GET, POST"},
                    )
                return

            is_known_static = (
                resolve_static_file(self.path, static_dir=self.static_dir) is not None
            )
            if method == "GET":
                self._handle_get(clean_path)
            elif method == "POST":
                self.close_connection = True
                if is_known_static:
                    self._send_json(
                        405,
                        {"error": "Method not allowed."},
                        extra_headers={"Allow": "GET"},
                    )
                else:
                    self._send_json(404, {"error": "Not found."})
            else:
                allow = "GET" if is_known_static else "GET, POST"
                self.close_connection = True
                self._send_json(
                    405,
                    {"error": "Method not allowed."},
                    extra_headers={"Allow": allow},
                )
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            raise
        except Exception:
            logger.exception("Unhandled error in request handler.")
            self.close_connection = True
            self._send_json(500, {"error": "Internal server error."})

    def handle_one_request(self) -> None:
        """Read, parse, and dispatch one HTTP request with per-connection timeout."""
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ""
                self.request_version = ""
                self.command = ""
                self.send_error(HTTPStatus.REQUEST_URI_TOO_LONG)
                return
            if not self.raw_requestline:
                self.close_connection = True
                return
            if not self.parse_request():
                return
            self._dispatch_request()
            self.wfile.flush()
        except TimeoutError:
            logger.warning("Client connection timed out.")
            self.close_connection = True
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def do_GET(self) -> None:
        """Handle GET requests through the central guarded dispatcher."""
        self._dispatch_request()

    def do_POST(self) -> None:
        """Handle POST requests through the central guarded dispatcher."""
        self._dispatch_request()


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
    allow_remote: bool = False,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
) -> ThreadingHTTPServer:
    """Create a configured ThreadingHTTPServer bound to (host, port)."""
    if not allow_remote and not is_loopback_host(host):
        raise ValueError(
            f"Refusing to bind non-loopback host {host!r} without allow_remote=True."
        )
    if not math.isfinite(request_timeout) or request_timeout <= 0:
        raise ValueError("request_timeout must be a positive finite number.")

    repo = _resolve_repository(repository=repository, data_dir=data_dir)
    bind_host = host.strip()
    if bind_host.startswith("[") and bind_host.endswith("]"):
        bind_host = bind_host[1:-1]

    class ConfiguredHandler(TravelSimRequestHandler):
        pass

    ConfiguredHandler.repository = repo
    ConfiguredHandler.data_dir = data_dir
    ConfiguredHandler.static_dir = static_dir
    ConfiguredHandler.max_body_bytes = max_body_bytes
    ConfiguredHandler.reference_time = reference_time
    ConfiguredHandler.clock = clock
    ConfiguredHandler.timeout = request_timeout

    addr_family = socket.AF_INET6 if ":" in bind_host else socket.AF_INET

    class ConfiguredServer(_LocalThreadingHTTPServer):
        address_family = addr_family

    return ConfiguredServer((bind_host, port), ConfiguredHandler)


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
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        default=False,
        help="Allow binding to non-loopback addresses (unsafe on untrusted networks).",
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

    is_loopback = is_loopback_host(args.host)
    if not is_loopback and not args.allow_remote:
        sys.stderr.write(
            f"Error: refusing to bind non-loopback host {args.host!r} without --allow-remote.\n"
        )
        return 2

    try:
        server = create_server(
            host=args.host,
            port=args.port,
            data_dir=args.data_dir,
            allow_remote=args.allow_remote,
        )
    except (
        FileNotFoundError,
        NotADirectoryError,
        RepositoryValidationError,
        ValueError,
        OSError,
    ) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 2

    if not is_loopback and args.allow_remote:
        sys.stderr.write(
            f"Warning: --allow-remote enabled; binding to non-loopback host {args.host!r}.\n"
        )
        sys.stderr.flush()

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
    "DEFAULT_REQUEST_TIMEOUT",
    "MAX_DATA_GB",
    "MAX_DAYS",
    "MAX_REQUEST_BODY_BYTES",
    "MIN_DATA_GB",
    "MIN_DAYS",
    "STATIC_DIR",
    "TravelSimRequestHandler",
    "build_parser",
    "create_server",
    "handle_cities",
    "handle_simulate",
    "handle_simulate_bytes",
    "handle_static",
    "is_loopback_host",
    "main",
    "resolve_static_file",
]


if __name__ == "__main__":
    raise SystemExit(main())
