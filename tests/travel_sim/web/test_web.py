"""Unit and socket integration tests for travel_sim.web and static UI assets."""
from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import travel_sim.web as web_module
from travel_sim.application.simulate import simulate
from travel_sim.cli import DEFAULT_DATA_DIR, simulation_to_dict
from travel_sim.domain import DeviceProfile, FrictionTolerance
from travel_sim.infrastructure.json_repository import (
    JsonOptionRepository,
    RepositoryValidationError,
)
from travel_sim.web import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_REQUEST_TIMEOUT,
    MAX_REQUEST_BODY_BYTES,
    STATIC_DIR,
    build_parser,
    create_server,
    handle_cities,
    handle_simulate,
    handle_simulate_bytes,
    handle_static,
    main,
    resolve_static_file,
)

FIXED_REF_TIME = datetime(2026, 11, 25, 12, 0, 0, tzinfo=UTC)
EXPECTED_HTML_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


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


def _build_verified_repo() -> JsonOptionRepository:
    repo = JsonOptionRepository()
    repo.load_dict(
        {
            "city": {
                "id": "scl",
                "name": "Santiago",
                "country_code": "CL",
                "local_currency": "CLP",
                "default_usd_exchange_rate": "950",
                "last_verified_at": "2026-06-01T00:00:00Z",
            },
            "options": [
                {
                    "id": "scl-conn-esim",
                    "city_id": "scl",
                    "category": "CONNECTIVITY",
                    "provider": "TestTel",
                    "name": "Test eSIM 20GB",
                    "cost_local_currency": "19000",
                    "cost_usd_reference": "20",
                    "pricing_model": "ONE_TIME_PACKAGE",
                    "validity_days": 30,
                    "data_quota_gb": "20",
                    "setup_time_minutes": 5,
                    "paperwork_level": 0,
                    "language_barrier_level": 0,
                    "physical_presence_required": False,
                    "uncertainty_risk_level": 0,
                    "requires_local_id": False,
                    "sim_type": "ESIM",
                    "is_tourist_friendly": True,
                    "last_verified_at": "2026-06-01T00:00:00Z",
                    "verification_source_url": "verified-source:esim-catalog",
                }
            ],
        }
    )
    return repo


def _start_server(**kwargs: Any) -> tuple[Any, str, int, threading.Thread]:
    server = create_server(host="127.0.0.1", port=0, **kwargs)
    bound_host, bound_port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, str(bound_host), int(bound_port), thread


def _stop_server(server: Any, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2.0)


@pytest.fixture()
def live_server() -> Iterator[tuple[Any, str, int]]:
    server, host, port, thread = _start_server(request_timeout=0.4)
    try:
        yield server, host, port
    finally:
        _stop_server(server, thread)


def _raw_http_exchange(
    host: str,
    port: int,
    raw_request: bytes,
    *,
    shutdown_write: bool = True,
    timeout: float = 2.0,
) -> tuple[int, dict[str, str], list[tuple[str, str]], bytes]:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(raw_request)
        if shutdown_write:
            sock.shutdown(socket.SHUT_WR)
        chunks: list[bytes] = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
    raw_response = b"".join(chunks)
    head, _, body = raw_response.partition(b"\r\n\r\n")
    lines = head.decode("iso-8859-1").split("\r\n")
    status_code = int(lines[0].split(" ", 2)[1])
    header_list: list[tuple[str, str]] = []
    header_dict: dict[str, str] = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        key = name.strip().lower()
        val = value.strip()
        header_list.append((key, val))
        header_dict[key] = val
    return status_code, header_dict, header_list, body


def _build_request(
    method: str,
    path: str,
    *,
    host_header: str | None,
    headers: list[tuple[str, str]] | None = None,
    body: bytes = b"",
) -> bytes:
    lines = [f"{method} {path} HTTP/1.1"]
    if host_header is not None:
        lines.append(f"Host: {host_header}")
    lines.append("Connection: close")
    if headers:
        for name, value in headers:
            lines.append(f"{name}: {value}")
    raw_head = ("\r\n".join(lines) + "\r\n\r\n").encode("iso-8859-1")
    return raw_head + body


_UNSET: Any = object()


def _post_json(
    host: str,
    port: int,
    path: str,
    body: bytes,
    *,
    host_header: Any = _UNSET,
    origin: str | None = None,
    content_type: str | None = "application/json",
) -> tuple[int, dict[str, str], list[tuple[str, str]], bytes]:
    req_headers: list[tuple[str, str]] = []
    if content_type is not None:
        req_headers.append(("Content-Type", content_type))
    if origin is not None:
        req_headers.append(("Origin", origin))
    req_headers.append(("Content-Length", str(len(body))))
    effective_host = f"{host}:{port}" if host_header is _UNSET else host_header
    raw = _build_request(
        "POST",
        path,
        host_header=effective_host,
        headers=req_headers,
        body=body,
    )
    return _raw_http_exchange(host, port, raw)


def _assert_security_headers(headers: dict[str, str], *, expect_html_csp: bool = False) -> None:
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("referrer-policy") == "no-referrer"
    server_header = headers.get("server", "")
    assert "Python" not in server_header
    assert "BaseHTTP" not in server_header
    assert not any(k.startswith("access-control-") for k in headers)
    if expect_html_csp:
        assert headers.get("content-security-policy") == EXPECTED_HTML_CSP


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
        _valid_payload(days=366),
        _valid_payload(days=True),
        _valid_payload(days=3.5),
        _valid_payload(days="7"),
        _valid_payload(data_gb=-1),
        _valid_payload(data_gb=1000.01),
        _valid_payload(data_gb="not-a-number"),
        _valid_payload(data_gb="NaN"),
        _valid_payload(data_gb="Infinity"),
        _valid_payload(data_gb=float("nan")),
        _valid_payload(data_gb=float("inf")),
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
        _valid_payload(reference_time=""),
        _valid_payload(reference_time="2026-11-25T12:00:00"),
        _valid_payload(reference_time="2026-11-25"),
        _valid_payload(reference_time="not-a-date"),
        _valid_payload(reference_time=12345),
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
    assert 'File "' not in serialized


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
        "//etc/passwd",
        "/static//../../cli.py",
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
    assert args.allow_remote is False

    custom_args = parser.parse_args(["--host", "127.0.0.1", "--port", "9090"])
    assert custom_args.host == "127.0.0.1"
    assert custom_args.port == 9090


def test_server_defaults_timeout_and_daemon_threads(
    live_server: tuple[Any, str, int],
) -> None:
    server, _host, _port = live_server
    assert server.daemon_threads is True
    assert DEFAULT_REQUEST_TIMEOUT == 10.0
    assert server.RequestHandlerClass.timeout == 0.4


@pytest.mark.parametrize(
    "bad_host",
    ["0.0.0.0", "::", "192.168.1.50", "example.com", ""],
)
def test_non_loopback_host_refused_without_allow_remote(
    bad_host: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(ValueError, match="non-loopback"):
        create_server(host=bad_host, port=0)

    rc = main(["--host", bad_host, "--port", "0"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "--allow-remote" in captured.err


def test_main_allows_non_loopback_with_allow_remote_and_warns_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    real_create_server = create_server
    seen_allow_remote: list[bool] = []

    def fake_create_server(*args: Any, **kwargs: Any) -> Any:
        seen_allow_remote.append(bool(kwargs.get("allow_remote", False)))
        kwargs["port"] = 0
        srv = real_create_server(*args, **kwargs)
        monkeypatch.setattr(srv, "serve_forever", lambda: None)
        return srv

    monkeypatch.setattr(web_module, "create_server", fake_create_server)
    rc = main(["--host", "0.0.0.0", "--allow-remote"])
    captured = capsys.readouterr()

    assert rc == 0
    assert seen_allow_remote == [True]
    assert "Warning" in captured.err
    assert "--allow-remote" in captured.err


@pytest.mark.parametrize(
    "traversal_path",
    [
        "/%2e%2e/cli.py",
        "/%2e%2e/%2e%2e/pyproject.toml",
        "/static/%2e%2e/%2e%2e/travel_sim/web.py",
        "/..%2fcli.py",
        "//etc/passwd",
        "//../cli.py",
        "/static//../../cli.py",
        "/%2f%2f../cli.py",
        "/%5c..%5ccli.py",
        "/\\..\\cli.py",
        "/index.html%00.txt",
        "/index.html\x00.txt",
    ],
)
def test_socket_blocks_path_traversal_variants(
    live_server: tuple[Any, str, int],
    traversal_path: str,
) -> None:
    _server, host, port = live_server
    raw = _build_request("GET", traversal_path, host_header=f"{host}:{port}")
    status, headers, _hlist, body = _raw_http_exchange(host, port, raw)
    assert status == 404
    _assert_security_headers(headers)
    assert b"def " not in body
    assert b"pyproject" not in body


def test_socket_blocks_symlink_escape_outside_static_dir(tmp_path: Path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("TOP_SECRET_MARKER", encoding="utf-8")
    (static_dir / "escape.txt").symlink_to(secret_file)

    server, host, port, thread = _start_server(static_dir=static_dir, request_timeout=0.4)
    try:
        raw_ok = _build_request("GET", "/index.html", host_header=f"{host}:{port}")
        status_ok, headers_ok, _h1, body_ok = _raw_http_exchange(host, port, raw_ok)
        assert status_ok == 200
        _assert_security_headers(headers_ok, expect_html_csp=True)
        assert b"ok" in body_ok

        raw_escape = _build_request("GET", "/escape.txt", host_header=f"{host}:{port}")
        status_esc, headers_esc, _h2, body_esc = _raw_http_exchange(host, port, raw_escape)
        assert status_esc == 404
        _assert_security_headers(headers_esc)
        assert b"TOP_SECRET_MARKER" not in body_esc
    finally:
        _stop_server(server, thread)


def test_socket_body_cap_missing_duplicate_and_transfer_encoding(
    live_server: tuple[Any, str, int],
) -> None:
    _server, host, port = live_server

    # Exact cap (16384 bytes) succeeds
    base_body = json.dumps(_valid_payload()).encode("utf-8")
    padded_body = base_body + b" " * (MAX_REQUEST_BODY_BYTES - len(base_body))
    assert len(padded_body) == MAX_REQUEST_BODY_BYTES
    status_ok, _h_ok, _hl_ok, _b_ok = _post_json(host, port, "/api/simulate", padded_body)
    assert status_ok == 200

    # Above cap (16385 bytes) rejected with 400
    raw_over = _build_request(
        "POST",
        "/api/simulate",
        host_header=f"{host}:{port}",
        headers=[
            ("Content-Type", "application/json"),
            ("Content-Length", str(MAX_REQUEST_BODY_BYTES + 1)),
        ],
        body=b"{}",
    )
    status_over, hdr_over, _hl, body_over = _raw_http_exchange(host, port, raw_over)
    assert status_over == 400
    _assert_security_headers(hdr_over)
    assert "exceeds limit" in json.loads(body_over)["error"]

    # Missing Content-Length rejected with 411
    raw_missing_cl = _build_request(
        "POST",
        "/api/simulate",
        host_header=f"{host}:{port}",
        headers=[("Content-Type", "application/json")],
        body=b"{}",
    )
    status_411, hdr_411, _hl, _b_411 = _raw_http_exchange(host, port, raw_missing_cl)
    assert status_411 == 411
    _assert_security_headers(hdr_411)

    # Duplicate Content-Length (same and conflicting) rejected with 400
    for cl_pair in ([("Content-Length", "2"), ("Content-Length", "2")],
                    [("Content-Length", "2"), ("Content-Length", "5")]):
        raw_dup = _build_request(
            "POST",
            "/api/simulate",
            host_header=f"{host}:{port}",
            headers=[("Content-Type", "application/json"), *cl_pair],
            body=b"{}",
        )
        status_dup, hdr_dup, _hl, _b_dup = _raw_http_exchange(host, port, raw_dup)
        assert status_dup == 400
        _assert_security_headers(hdr_dup)

    # Transfer-Encoding rejected with 400
    raw_te = _build_request(
        "POST",
        "/api/simulate",
        host_header=f"{host}:{port}",
        headers=[
            ("Content-Type", "application/json"),
            ("Transfer-Encoding", "chunked"),
        ],
        body=b"2\r\n{}\r\n0\r\n\r\n",
    )
    status_te, hdr_te, _hl, _b_te = _raw_http_exchange(host, port, raw_te)
    assert status_te == 400
    _assert_security_headers(hdr_te)


def test_socket_lying_content_length_truncated_and_timeout(
    live_server: tuple[Any, str, int],
) -> None:
    _server, host, port = live_server

    # Truncated body (client closes write side early)
    raw_trunc = _build_request(
        "POST",
        "/api/simulate",
        host_header=f"{host}:{port}",
        headers=[("Content-Type", "application/json"), ("Content-Length", "100")],
        body=b'{"city":"scl"}',
    )
    status_trunc, hdr_trunc, _hl, body_trunc = _raw_http_exchange(host, port, raw_trunc)
    assert status_trunc == 400
    _assert_security_headers(hdr_trunc)
    assert "Incomplete" in json.loads(body_trunc)["error"]

    # Stalling lying Content-Length (socket left open): server times out cleanly
    raw_stall = _build_request(
        "POST",
        "/api/simulate",
        host_header=f"{host}:{port}",
        headers=[("Content-Type", "application/json"), ("Content-Length", "100")],
        body=b'{"city":"s',
    )
    started = time.monotonic()
    status_stall, hdr_stall, _hl, _body_stall = _raw_http_exchange(
        host,
        port,
        raw_stall,
        shutdown_write=False,
        timeout=1.5,
    )
    elapsed = time.monotonic() - started
    assert status_stall == 408
    assert elapsed < 1.3
    _assert_security_headers(hdr_stall)

    # Server stays responsive after timed-out request
    raw_after = _build_request("GET", "/api/cities", host_header=f"{host}:{port}")
    status_after, _hdr_after, _hl, _b_after = _raw_http_exchange(host, port, raw_after)
    assert status_after == 200


def test_socket_host_origin_and_content_type_checks(
    live_server: tuple[Any, str, int],
) -> None:
    _server, host, port = live_server
    valid_body = json.dumps(_valid_payload()).encode("utf-8")

    # Allowed Host header variants
    for allowed_host in (
        "localhost",
        f"localhost:{port}",
        "127.0.0.1",
        f"127.0.0.1:{port}",
        "[::1]",
        f"[::1]:{port}",
    ):
        raw_get = _build_request("GET", "/api/cities", host_header=allowed_host)
        status, headers, _hl, _body = _raw_http_exchange(host, port, raw_get)
        assert status == 200
        _assert_security_headers(headers)

    # Disallowed Host headers (DNS rebinding)
    for bad_host in (
        None,
        "evil.com",
        f"evil.com:{port}",
        "127.0.0.1.evil.com",
        f"192.168.1.2:{port}",
        "localhost:abc",
    ):
        raw_get = _build_request("GET", "/", host_header=bad_host)
        status, headers, _hl, _body = _raw_http_exchange(host, port, raw_get)
        assert status == 403
        _assert_security_headers(headers)

        status_post, hdr_post, _hl, _b = _post_json(
            host,
            port,
            "/api/simulate",
            valid_body,
            host_header=bad_host,
        )
        assert status_post == 403
        _assert_security_headers(hdr_post)

    # Duplicate Host header rejected with 403
    raw_dup_host = _build_request(
        "GET",
        "/api/cities",
        host_header=f"{host}:{port}",
        headers=[("Host", "localhost")],
    )
    status_dup_host, hdr_dup_host, _hl, _b = _raw_http_exchange(host, port, raw_dup_host)
    assert status_dup_host == 403
    _assert_security_headers(hdr_dup_host)

    # Origin checks on POST
    status_same, hdr_same, _hl, _b = _post_json(
        host,
        port,
        "/api/simulate",
        valid_body,
        origin=f"http://127.0.0.1:{port}",
    )
    assert status_same == 200
    _assert_security_headers(hdr_same)

    status_local, hdr_local, _hl, _b = _post_json(
        host,
        port,
        "/api/simulate",
        valid_body,
        host_header=f"localhost:{port}",
        origin=f"http://localhost:{port}",
    )
    assert status_local == 200
    _assert_security_headers(hdr_local)

    for bad_origin in (
        "http://evil.com",
        f"http://127.0.0.1:{port + 1}",
        f"https://127.0.0.1:{port}",
        "null",
    ):
        status_bad_origin, hdr_bad_origin, _hl, _b = _post_json(
            host,
            port,
            "/api/simulate",
            valid_body,
            origin=bad_origin,
        )
        assert status_bad_origin == 403
        _assert_security_headers(hdr_bad_origin)

    # Content-Type checks on POST
    for bad_ct in (None, "text/plain", "application/x-www-form-urlencoded"):
        status_ct, hdr_ct, _hl, _b = _post_json(
            host,
            port,
            "/api/simulate",
            valid_body,
            content_type=bad_ct,
        )
        assert status_ct == 415
        _assert_security_headers(hdr_ct)

    status_charset, _hdr_charset, _hl, _b = _post_json(
        host,
        port,
        "/api/simulate",
        valid_body,
        content_type="application/json; charset=utf-8",
    )
    assert status_charset == 200


@pytest.mark.parametrize(
    ("method", "path", "expected_allow"),
    [
        ("GET", "/api/simulate", "POST"),
        ("POST", "/api/cities", "GET"),
        ("POST", "/", "GET"),
        ("POST", "/index.html", "GET"),
        ("PUT", "/api/simulate", "POST"),
        ("DELETE", "/api/cities", "GET"),
        ("PATCH", "/", "GET"),
        ("OPTIONS", "/api/simulate", "POST"),
        ("HEAD", "/api/cities", "GET"),
        ("PUT", "/unknown-path", "GET, POST"),
    ],
)
def test_socket_405_with_allow_and_security_headers(
    live_server: tuple[Any, str, int],
    method: str,
    path: str,
    expected_allow: str,
) -> None:
    _server, host, port = live_server
    raw = _build_request(method, path, host_header=f"{host}:{port}")
    status, headers, _hl, body = _raw_http_exchange(host, port, raw)
    assert status == 405
    assert headers.get("allow") == expected_allow
    assert "application/json" in headers.get("content-type", "")
    _assert_security_headers(headers)
    if method != "HEAD":
        parsed = json.loads(body)
        assert "error" in parsed


def test_socket_security_headers_on_200_400_404_405(
    live_server: tuple[Any, str, int],
) -> None:
    _server, host, port = live_server

    # 200 HTML
    raw_html = _build_request("GET", "/", host_header=f"{host}:{port}")
    s_html, h_html, _hl, _b_html = _raw_http_exchange(host, port, raw_html)
    assert s_html == 200
    _assert_security_headers(h_html, expect_html_csp=True)

    # 200 JS
    raw_js = _build_request("GET", "/app.js", host_header=f"{host}:{port}")
    s_js, h_js, _hl, _b_js = _raw_http_exchange(host, port, raw_js)
    assert s_js == 200
    _assert_security_headers(h_js)

    # 400
    s_400, h_400, _hl, _b_400 = _post_json(
        host,
        port,
        "/api/simulate",
        json.dumps(_valid_payload(days=0)).encode("utf-8"),
    )
    assert s_400 == 400
    _assert_security_headers(h_400)

    # 404
    raw_404 = _build_request("GET", "/api/does-not-exist", host_header=f"{host}:{port}")
    s_404, h_404, _hl, _b_404 = _raw_http_exchange(host, port, raw_404)
    assert s_404 == 404
    _assert_security_headers(h_404)


def test_error_bodies_never_leak_paths_or_exception_internals(tmp_path: Path) -> None:
    secret_dir = tmp_path / "secret_missing_catalog_dir"
    status_c, data_c = handle_cities({}, data_dir=secret_dir)
    assert status_c == 500
    assert "secret_missing_catalog_dir" not in json.dumps(data_c)
    assert str(tmp_path) not in json.dumps(data_c)

    status_s, data_s = handle_simulate(_valid_payload(), data_dir=secret_dir)
    assert status_s == 500
    assert "secret_missing_catalog_dir" not in json.dumps(data_s)
    assert str(tmp_path) not in json.dumps(data_s)

    class BrokenRepo:
        def list_cities(self) -> list[Any]:
            raise FileNotFoundError("/var/secret/private_catalog/cities.json")

        def get_city(self, city_id: str) -> Any:
            del city_id
            raise RepositoryValidationError("Invalid JSON in /var/secret/private_catalog/scl.json")

    broken_repo: Any = BrokenRepo()
    server_broken, host, port, thread = _start_server(repository=broken_repo)
    try:
        raw_cities = _build_request("GET", "/api/cities", host_header=f"{host}:{port}")
        sc, _hc, _hl, bc = _raw_http_exchange(host, port, raw_cities)
        assert sc == 500
        assert b"/var/secret" not in bc
        assert b"cities.json" not in bc

        ss, _hs, _hl, bs = _post_json(
            host,
            port,
            "/api/simulate",
            json.dumps(_valid_payload()).encode("utf-8"),
        )
        assert ss == 500
        assert b"/var/secret" not in bs
        assert b"scl.json" not in bs
    finally:
        _stop_server(server_broken, thread)

    # Engine ValueError (reference_time before last_verified_at) must return generic 400
    repo = _build_verified_repo()
    server_ver, v_host, v_port, v_thread = _start_server(repository=repo)
    try:
        se, _he, _hl, be = _post_json(
            v_host,
            v_port,
            "/api/simulate",
            json.dumps(_valid_payload(reference_time="2020-01-01T00:00:00Z")).encode("utf-8"),
        )
        assert se == 400
        assert b"last_verified_at" not in be
        assert b"Traceback" not in be
        assert json.loads(be)["error"] == "Invalid simulation parameters."
    finally:
        _stop_server(server_ver, v_thread)


def test_socket_bounds_and_allow_nan_false(
    live_server: tuple[Any, str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _server, host, port = live_server

    for valid_overrides in ({"days": 1, "data_gb": 0}, {"days": 365, "data_gb": 1000}):
        status, _hdr, _hl, _body = _post_json(
            host,
            port,
            "/api/simulate",
            json.dumps(_valid_payload(**valid_overrides)).encode("utf-8"),
        )
        assert status == 200

    for bad_overrides, expected_field in (
        ({"days": 0}, "days"),
        ({"days": 366}, "days"),
        ({"data_gb": -0.01}, "data_gb"),
        ({"data_gb": 1000.01}, "data_gb"),
        ({"data_gb": "NaN"}, "data_gb"),
        ({"data_gb": "Infinity"}, "data_gb"),
    ):
        status, _hdr, _hl, body = _post_json(
            host,
            port,
            "/api/simulate",
            json.dumps(_valid_payload(**bad_overrides)).encode("utf-8"),
        )
        assert status == 400
        assert json.loads(body)["field"] == expected_field

    for raw_bad in (
        (
            b'{"city":"scl","days":7,"data_gb":NaN,'
            b'"device":"dual","has_local_id":false,"tolerance":"MEDIUM"}'
        ),
        (
            b'{"city":"scl","days":7,"data_gb":Infinity,'
            b'"device":"dual","has_local_id":false,"tolerance":"MEDIUM"}'
        ),
    ):
        status_nan, _hdr, _hl, _body = _post_json(host, port, "/api/simulate", raw_bad)
        assert status_nan == 400

    # Ensure allow_nan=False prevents sending Infinity in any HTTP JSON response
    monkeypatch.setattr(
        web_module,
        "simulation_to_dict",
        lambda *_args, **_kwargs: {"bad_float": float("inf")},
    )
    status_inf, _hdr_inf, _hl, body_inf = _post_json(
        host,
        port,
        "/api/simulate",
        json.dumps(_valid_payload()).encode("utf-8"),
    )
    assert status_inf == 500
    assert b"Infinity" not in body_inf
    assert json.loads(body_inf) == {"error": "Internal server error."}


def test_socket_reference_time_determinism() -> None:
    repo = _build_verified_repo()
    server, host, port, thread = _start_server(repository=repo)
    try:
        fresh_body = json.dumps(
            _valid_payload(reference_time="2026-06-15T12:00:00Z")
        ).encode("utf-8")
        s1, _h1, _hl1, b1 = _post_json(host, port, "/api/simulate", fresh_body)
        s2, _h2, _hl2, b2 = _post_json(host, port, "/api/simulate", fresh_body)
        assert s1 == 200
        assert s2 == 200
        assert b1 == b2
        fresh_data = json.loads(b1)
        assert fresh_data["city"]["freshness_status"] == "FRESH"
        assert fresh_data["expired_option_ids"] == []

        expired_body = json.dumps(
            _valid_payload(reference_time="2027-06-15T12:00:00Z")
        ).encode("utf-8")
        s_exp, _h_exp, _hl_exp, b_exp = _post_json(host, port, "/api/simulate", expired_body)
        assert s_exp == 200
        expired_data = json.loads(b_exp)
        assert expired_data["city"]["freshness_status"] == "EXPIRED"
        assert expired_data["expired_option_ids"] == ["scl-conn-esim"]

        # Timezone-less ISO 8601 must be rejected
        naive_body = json.dumps(
            _valid_payload(reference_time="2026-06-15T12:00:00")
        ).encode("utf-8")
        s_naive, _h_n, _hl_n, b_naive = _post_json(host, port, "/api/simulate", naive_body)
        assert s_naive == 400
        assert json.loads(b_naive)["field"] == "reference_time"
    finally:
        _stop_server(server, thread)


def test_ui_assets_enforce_bounds_accessibility_and_error_handling() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'aria-labelledby="rejected-heading"' in html or "<caption" in html
    assert "days > 365" in js
    assert "dataGb > 1000" in js
    assert "aria-invalid" in js
    assert ".focus()" in js
    assert "clearPreviousResults" in js
    assert "JSON.parse(rawText)" in js
    assert "los metadatos de la ciudad superaron la ventana" in js
    assert "los metadatos de la ciudad se encuentran en la ventana" in js
