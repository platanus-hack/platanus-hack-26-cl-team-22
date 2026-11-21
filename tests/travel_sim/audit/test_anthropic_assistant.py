"""Tests for the urllib-based AnthropicAssistant adapter."""
from __future__ import annotations

import email
import http.client
import io
import json
import traceback
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
from collections.abc import Mapping

import pytest

from travel_sim.application.ports import AssistantPort
from travel_sim.infrastructure.anthropic_assistant import (
    API_KEY_ENV_VAR,
    BASE_URL_ENV_VAR,
    MAX_RESPONSE_BYTES,
    AnthropicAPIError,
    AnthropicAssistant,
    AnthropicAssistantError,
    AnthropicTimeoutError,
    TransportResponse,
    _urllib_transport,
)
from travel_sim.infrastructure.replay_assistant import BudgetExceededError

FAKE_SECRET = "dummy-test-token-value-98765"
FAKE_URL_TOKEN = "secret-proxy-tok-54321"
FAKE_BASE_URL = f"https://proxy.example.test/{FAKE_URL_TOKEN}"


def _ok_response(content_blocks: list[dict[str, object]]) -> TransportResponse:
    payload = {
        "id": "msg_test_1",
        "type": "message",
        "role": "assistant",
        "content": content_blocks,
    }
    return TransportResponse(
        status_code=200,
        body=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
    )


def _assert_no_secrets_leaked(exc: BaseException) -> None:
    formatted_tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    for text in (str(exc), repr(exc), formatted_tb):
        lowered = text.lower()
        assert FAKE_SECRET.lower() not in lowered
        assert FAKE_SECRET[:12].lower() not in lowered
        assert FAKE_BASE_URL.lower() not in lowered
        assert f"/{FAKE_URL_TOKEN}".lower() not in lowered
        assert FAKE_URL_TOKEN.lower() not in lowered
    assert exc.__cause__ is None
    assert exc.__context__ is None


def test_implements_assistant_port() -> None:
    assistant = AnthropicAssistant("claude-sonnet-4-20250514")
    assert isinstance(assistant, AssistantPort)


def test_request_shape_headers_and_concatenated_text_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    monkeypatch.delenv(BASE_URL_ENV_VAR, raising=False)

    recorded: list[tuple[str, Mapping[str, str], bytes, float]] = []

    def fake_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        recorded.append((url, dict(headers), body, timeout))
        return _ok_response(
            [
                {"type": "thinking", "thinking": "ignored"},
                {"type": "text", "text": '{"CONNECTIVITY": '},
                {"type": "text", "text": '"scl-conn-wom-plan-zero-esim"}'},
            ]
        )

    assistant = AnthropicAssistant(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        timeout=12.5,
        transport=fake_transport,
    )

    reply = assistant.ask("Choose options", "bot:rep-0")
    assert reply == '{"CONNECTIVITY": "scl-conn-wom-plan-zero-esim"}'
    assert len(recorded) == 1

    url, headers, body, timeout = recorded[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert timeout == 12.5
    assert headers["x-api-key"] == FAKE_SECRET
    assert headers["anthropic-version"] == "2023-06-01"
    assert headers["content-type"] == "application/json"

    parsed_body = json.loads(body.decode("utf-8"))
    assert parsed_body == {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 512,
        "temperature": 0,
        "messages": [{"role": "user", "content": "Choose options"}],
    }


def test_base_url_and_api_key_read_at_call_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
    monkeypatch.delenv(BASE_URL_ENV_VAR, raising=False)

    seen_calls: list[tuple[str, str]] = []

    def fake_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        del body, timeout
        seen_calls.append((url, headers["x-api-key"]))
        return _ok_response([{"type": "text", "text": "ok"}])

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=fake_transport,
    )

    with pytest.raises(AnthropicAssistantError, match=API_KEY_ENV_VAR):
        assistant.ask("hello", "rep-0")

    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    monkeypatch.setenv(BASE_URL_ENV_VAR, "https://proxy.example.test/api/")
    assert assistant.ask("hello", "rep-0") == "ok"

    second_secret = "dummy-test-token-rotated-11111"
    monkeypatch.setenv(API_KEY_ENV_VAR, second_secret)
    monkeypatch.setenv(BASE_URL_ENV_VAR, "https://proxy2.example.test")
    assert assistant.ask("hello", "rep-1") == "ok"

    assert seen_calls == [
        ("https://proxy.example.test/api/v1/messages", FAKE_SECRET),
        ("https://proxy2.example.test/v1/messages", second_secret),
    ]


def test_secret_and_base_url_token_never_appear_in_repr_vars_or_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    monkeypatch.setenv(BASE_URL_ENV_VAR, FAKE_BASE_URL)

    def bad_transport(
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
                    "type": "error",
                    "error": {
                        "type": "authentication_error",
                        "message": (
                            f"Invalid key {FAKE_SECRET} at {url} "
                            f"base={FAKE_BASE_URL} path=/{FAKE_URL_TOKEN} tok={FAKE_URL_TOKEN}"
                        ),
                    },
                }
            ).encode("utf-8"),
        )

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        max_tokens=256,
        timeout=5.0,
        transport=bad_transport,
    )

    for representation in (repr(assistant), str(assistant), repr(vars(assistant))):
        assert FAKE_SECRET not in representation
        assert FAKE_BASE_URL not in representation
        assert FAKE_URL_TOKEN not in representation

    with pytest.raises(AnthropicAPIError) as exc_info:
        assistant.ask("hello", "rep-0")

    assert exc_info.value.status_code == 401
    _assert_no_secrets_leaked(exc_info.value)


def test_redaction_happens_before_truncation_and_on_urlerror_and_malformed_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    monkeypatch.setenv(BASE_URL_ENV_VAR, FAKE_BASE_URL)

    # Place secrets across the 200-character truncation boundary in raw error text.
    boundary_body = ("x" * 190 + f" key={FAKE_SECRET} url={FAKE_BASE_URL}").encode("utf-8")
    assistant_raw_err = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=lambda url, headers, body, timeout: TransportResponse(
            status_code=400,
            body=boundary_body,
        ),
    )
    with pytest.raises(AnthropicAPIError) as exc_raw:
        assistant_raw_err.ask("hello", "rep-0")
    _assert_no_secrets_leaked(exc_raw.value)

    # URLError reason containing both the API key and base URL token.
    def urlerror_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        del headers, body, timeout
        raise urllib.error.URLError(
            f"failed connecting to {url} (token={FAKE_URL_TOKEN}, key={FAKE_SECRET})"
        )

    assistant_urlerr = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=urlerror_transport,
    )
    with pytest.raises(AnthropicAssistantError) as exc_url:
        assistant_urlerr.ask("hello", "rep-0")
    _assert_no_secrets_leaked(exc_url.value)

    # Malformed 200 JSON body containing the API key and base URL token.
    malformed_body = f"not-json {FAKE_SECRET} {FAKE_BASE_URL} {FAKE_URL_TOKEN}".encode()
    assistant_malformed = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=lambda url, headers, body, timeout: TransportResponse(
            status_code=200,
            body=malformed_body,
        ),
    )
    with pytest.raises(AnthropicAssistantError) as exc_malformed:
        assistant_malformed.ask("hello", "rep-0")
    _assert_no_secrets_leaked(exc_malformed.value)


@pytest.mark.parametrize(
    ("exc_to_raise", "expected_type_name"),
    [
        (
            ValueError(f"bad url {FAKE_BASE_URL} key={FAKE_SECRET}"),
            "ValueError",
        ),
        (
            http.client.InvalidURL(f"nonnumeric port in {FAKE_BASE_URL} key={FAKE_SECRET}"),
            "InvalidURL",
        ),
        (
            http.client.IncompleteRead(f"{FAKE_SECRET} {FAKE_URL_TOKEN}".encode(), 100),
            "IncompleteRead",
        ),
        (
            OSError(f"socket failure to {FAKE_BASE_URL} key={FAKE_SECRET}"),
            "OSError",
        ),
    ],
)
def test_transport_low_level_exceptions_are_wrapped_with_type_name_only(
    monkeypatch: pytest.MonkeyPatch,
    exc_to_raise: Exception,
    expected_type_name: str,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    monkeypatch.setenv(BASE_URL_ENV_VAR, FAKE_BASE_URL)

    def failing_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        del url, headers, body, timeout
        raise exc_to_raise

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=failing_transport,
    )

    with pytest.raises(AnthropicAssistantError) as exc_info:
        assistant.ask("hello", "rep-0")

    assert expected_type_name in str(exc_info.value)
    assert "nonnumeric port" not in str(exc_info.value)
    assert "socket failure" not in str(exc_info.value)
    assert "bad url" not in str(exc_info.value)
    _assert_no_secrets_leaked(exc_info.value)


@pytest.mark.parametrize("redirect_code", [301, 302, 303, 307, 308])
def test_http_redirects_are_refused_without_forwarding_credentials(
    monkeypatch: pytest.MonkeyPatch,
    redirect_code: int,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    monkeypatch.setenv(BASE_URL_ENV_VAR, FAKE_BASE_URL)

    requested_urls: list[str] = []
    real_build_opener = urllib.request.build_opener

    class _FakeHTTPSHandler(urllib.request.HTTPSHandler):
        def https_open(self, req: urllib.request.Request) -> urllib.response.addinfourl:
            requested_urls.append(req.full_url)
            hdrs = email.message_from_string(
                f"Location: http://evil.example.test/steal?tok={FAKE_URL_TOKEN}\r\n"
            )
            response = urllib.response.addinfourl(
                io.BytesIO(b"redirecting"),
                hdrs,
                req.full_url,
                code=redirect_code,
            )
            response.msg = "Redirect"  # real responses carry .msg; HTTPErrorProcessor reads it
            return response

        def http_open(self, req: urllib.request.Request) -> urllib.response.addinfourl:
            requested_urls.append(req.full_url)
            raise AssertionError("Redirect target must never be requested")

    def patched_build_opener(*handlers: object) -> urllib.request.OpenerDirector:
        return real_build_opener(*handlers, _FakeHTTPSHandler())

    monkeypatch.setattr(urllib.request, "build_opener", patched_build_opener)

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=_urllib_transport,
    )

    with pytest.raises(AnthropicAssistantError, match="redirect") as exc_info:
        assistant.ask("hello", "rep-0")

    assert len(requested_urls) == 1
    assert "evil.example.test" not in str(exc_info.value)
    _assert_no_secrets_leaked(exc_info.value)


@pytest.mark.parametrize(
    "invalid_base_url",
    [
        f"http://remote.example.test/{FAKE_URL_TOKEN}",
        f"file:///etc/passwd/{FAKE_URL_TOKEN}",
        f"ftp://proxy.example.test/{FAKE_URL_TOKEN}",
        f"proxy.example.test/{FAKE_URL_TOKEN}",
        f"https://proxy.example.test/{FAKE_URL_TOKEN} with space",
        "   ",
    ],
)
def test_base_url_scheme_and_format_validation_rejects_unsafe_urls(
    monkeypatch: pytest.MonkeyPatch,
    invalid_base_url: str,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    monkeypatch.setenv(BASE_URL_ENV_VAR, invalid_base_url)

    transport_called = False

    def spy_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        nonlocal transport_called
        del url, headers, body, timeout
        transport_called = True
        return _ok_response([{"type": "text", "text": "ok"}])

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=spy_transport,
    )

    with pytest.raises(AnthropicAssistantError) as exc_info:
        assistant.ask("hello", "rep-0")

    assert not transport_called
    assert "remote.example.test" not in str(exc_info.value)
    assert "/etc/passwd" not in str(exc_info.value)
    _assert_no_secrets_leaked(exc_info.value)


@pytest.mark.parametrize(
    "local_base_url",
    [
        "http://localhost:8080/api",
        "http://127.0.0.1:9000",
    ],
)
def test_base_url_allows_http_for_localhost_and_loopback(
    monkeypatch: pytest.MonkeyPatch,
    local_base_url: str,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    monkeypatch.setenv(BASE_URL_ENV_VAR, local_base_url)

    seen_urls: list[str] = []

    def fake_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        del headers, body, timeout
        seen_urls.append(url)
        return _ok_response([{"type": "text", "text": "local-ok"}])

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=fake_transport,
    )
    assert assistant.ask("hello", "rep-0") == "local-ok"
    assert seen_urls == [f"{local_base_url.rstrip('/')}/v1/messages"]


def test_call_budget_counts_every_http_attempt_including_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)

    budget_calls = 0
    max_calls = 2
    transport_attempts = 0
    sleeps: list[float] = []

    def consume_budget(salt: str) -> None:
        nonlocal budget_calls
        if budget_calls >= max_calls:
            raise BudgetExceededError(f"Call budget cap of {max_calls} reached for {salt!r}")
        budget_calls += 1

    def always_429(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        nonlocal transport_attempts
        del url, headers, body, timeout
        transport_attempts += 1
        return TransportResponse(
            status_code=429,
            body=b'{"error":{"message":"rate limit"}}',
        )

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        max_retries=3,
        backoff_seconds=0.1,
        sleep=sleeps.append,
        transport=always_429,
        call_budget=consume_budget,
    )

    with pytest.raises(BudgetExceededError):
        assistant.ask("prompt", "rep-0")

    assert budget_calls == 2
    assert transport_attempts == 2
    assert sleeps == [0.1, 0.2]


def test_response_size_cap_enforced_at_one_mib(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)

    oversized_body = b"a" * (MAX_RESPONSE_BYTES + 1)
    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=lambda url, headers, body, timeout: TransportResponse(
            status_code=200,
            body=oversized_body,
        ),
    )
    with pytest.raises(AnthropicAssistantError, match=str(MAX_RESPONSE_BYTES)):
        assistant.ask("prompt", "rep-0")

    real_build_opener = urllib.request.build_opener

    class _OversizedStreamHandler(urllib.request.HTTPSHandler):
        def https_open(self, req: urllib.request.Request) -> urllib.response.addinfourl:
            response = urllib.response.addinfourl(
                io.BytesIO(oversized_body),
                email.message_from_string("Content-Type: application/json\r\n"),
                req.full_url,
                code=200,
            )
            response.msg = "OK"
            return response

    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *handlers: real_build_opener(*handlers, _OversizedStreamHandler()),
    )

    urllib_assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=_urllib_transport,
    )
    with pytest.raises(AnthropicAssistantError, match=str(MAX_RESPONSE_BYTES)):
        urllib_assistant.ask("prompt", "rep-0")


def test_retry_on_429_and_5xx_with_exponential_backoff_then_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)

    responses = iter(
        [
            TransportResponse(status_code=429, body=b'{"error":{"message":"rate limit"}}'),
            TransportResponse(status_code=503, body=b'{"error":{"message":"overloaded"}}'),
            _ok_response([{"type": "text", "text": "recovered"}]),
        ]
    )
    sleeps: list[float] = []
    attempts = 0

    def fake_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        nonlocal attempts
        del url, headers, body, timeout
        attempts += 1
        return next(responses)

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        max_retries=3,
        backoff_seconds=0.5,
        sleep=sleeps.append,
        transport=fake_transport,
    )

    reply = assistant.ask("prompt", "rep-0")
    assert reply == "recovered"
    assert attempts == 3
    assert sleeps == [0.5, 1.0]


def test_bounded_retries_exhausted_on_429_raises_error_without_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    monkeypatch.setenv(BASE_URL_ENV_VAR, FAKE_BASE_URL)
    sleeps: list[float] = []
    attempts = 0

    def always_429(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        nonlocal attempts
        del headers, body, timeout
        attempts += 1
        return TransportResponse(
            status_code=429,
            body=json.dumps(
                {"error": {"message": f"too many requests to {url} key={FAKE_SECRET}"}}
            ).encode("utf-8"),
        )

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        max_retries=2,
        backoff_seconds=0.25,
        sleep=sleeps.append,
        transport=always_429,
    )

    with pytest.raises(AnthropicAPIError) as exc_info:
        assistant.ask("prompt", "rep-0")

    assert exc_info.value.status_code == 429
    assert attempts == 3
    assert sleeps == [0.25, 0.5]
    _assert_no_secrets_leaked(exc_info.value)


def test_no_retry_on_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    sleeps: list[float] = []
    attempts = 0

    def always_400(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        nonlocal attempts
        del url, headers, body, timeout
        attempts += 1
        return TransportResponse(
            status_code=400,
            body=json.dumps(
                {
                    "type": "error",
                    "error": {"type": "invalid_request_error", "message": "bad payload"},
                }
            ).encode("utf-8"),
        )

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        max_retries=3,
        backoff_seconds=0.5,
        sleep=sleeps.append,
        transport=always_400,
    )

    with pytest.raises(AnthropicAPIError, match="400") as exc_info:
        assistant.ask("prompt", "rep-0")

    assert exc_info.value.status_code == 400
    assert "bad payload" in str(exc_info.value)
    assert attempts == 1
    assert sleeps == []
    assert FAKE_SECRET not in str(exc_info.value)


@pytest.mark.parametrize(
    "raised",
    [
        TimeoutError("read operation timed out"),
        urllib.error.URLError(TimeoutError("connect timed out")),
    ],
)
def test_timeout_handling_does_not_retry_and_leaks_no_secret(
    monkeypatch: pytest.MonkeyPatch,
    raised: Exception,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    monkeypatch.setenv(BASE_URL_ENV_VAR, FAKE_BASE_URL)
    sleeps: list[float] = []
    attempts = 0

    def timeout_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        nonlocal attempts
        del url, headers, body, timeout
        attempts += 1
        raise raised

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        timeout=3.5,
        max_retries=3,
        sleep=sleeps.append,
        transport=timeout_transport,
    )

    with pytest.raises(AnthropicTimeoutError, match="timed out") as exc_info:
        assistant.ask("prompt", "rep-0")

    assert attempts == 1
    assert sleeps == []
    _assert_no_secrets_leaked(exc_info.value)


def test_invalid_constructor_and_malformed_response_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError):
        AnthropicAssistant("")
    with pytest.raises(ValueError):
        AnthropicAssistant("claude-sonnet-4-20250514", max_tokens=0)
    with pytest.raises(ValueError):
        AnthropicAssistant("claude-sonnet-4-20250514", timeout=-1.0)
    with pytest.raises(ValueError):
        AnthropicAssistant("claude-sonnet-4-20250514", timeout=120.1)
    with pytest.raises(ValueError):
        AnthropicAssistant("claude-sonnet-4-20250514", max_retries=-1)
    with pytest.raises(ValueError):
        AnthropicAssistant("claude-sonnet-4-20250514", max_retries=6)
    with pytest.raises(ValueError):
        AnthropicAssistant("claude-sonnet-4-20250514", backoff_seconds=-0.1)
    with pytest.raises(ValueError):
        AnthropicAssistant("claude-sonnet-4-20250514", backoff_seconds=30.1)

    # Boundary upper limits succeed.
    boundary_ok = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        timeout=120.0,
        max_retries=5,
        backoff_seconds=30.0,
    )
    assert boundary_ok.timeout == 120.0
    assert boundary_ok.max_retries == 5

    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    empty_content = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=lambda url, headers, body, timeout: _ok_response(
            [{"type": "thinking", "thinking": "no text block"}]
        ),
    )
    with pytest.raises(AnthropicAssistantError, match="no text content blocks"):
        empty_content.ask("prompt", "rep-0")


def test_httperror_with_oversized_body_detaches_cause_context_and_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    monkeypatch.setenv(BASE_URL_ENV_VAR, FAKE_BASE_URL)

    oversized_body = (
        f"tok={FAKE_URL_TOKEN} url={FAKE_BASE_URL} key={FAKE_SECRET} ".encode("utf-8")
        + b"x" * (MAX_RESPONSE_BYTES + 64)
    )

    def raising_httperror_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        del headers, body, timeout
        raise urllib.error.HTTPError(
            url=url,
            code=502,
            msg=f"Bad Gateway for {url} ({FAKE_URL_TOKEN})",
            hdrs=email.message_from_string("Content-Type: text/plain\r\n"),
            fp=io.BytesIO(oversized_body),
        )

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=raising_httperror_transport,
    )

    with pytest.raises(AnthropicAssistantError, match=str(MAX_RESPONSE_BYTES)) as exc_info:
        assistant.ask("hello", "rep-0")

    exc = exc_info.value
    assert exc.__cause__ is None
    assert exc.__context__ is None
    formatted = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    for surface in (str(exc), repr(exc), repr(exc.__cause__), repr(exc.__context__), formatted):
        lowered = surface.lower()
        assert FAKE_URL_TOKEN.lower() not in lowered
        assert FAKE_BASE_URL.lower() not in lowered
        assert FAKE_SECRET.lower() not in lowered

    # Also exercise the _urllib_transport HTTPError oversized-body path.
    real_build_opener = urllib.request.build_opener

    class _OversizedErrorHandler(urllib.request.HTTPSHandler):
        def https_open(self, req: urllib.request.Request) -> urllib.response.addinfourl:
            response = urllib.response.addinfourl(
                io.BytesIO(oversized_body),
                email.message_from_string("Content-Type: text/plain\r\n"),
                req.full_url,
                code=502,
            )
            response.msg = f"Bad Gateway for {req.full_url} ({FAKE_URL_TOKEN})"
            return response

    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *handlers: real_build_opener(*handlers, _OversizedErrorHandler()),
    )

    urllib_assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=_urllib_transport,
    )
    with pytest.raises(AnthropicAssistantError, match=str(MAX_RESPONSE_BYTES)) as urllib_exc_info:
        urllib_assistant.ask("hello", "rep-0")

    urllib_exc = urllib_exc_info.value
    assert urllib_exc.__cause__ is None
    assert urllib_exc.__context__ is None
    urllib_formatted = "".join(
        traceback.format_exception(type(urllib_exc), urllib_exc, urllib_exc.__traceback__)
    )
    for surface in (
        str(urllib_exc),
        repr(urllib_exc),
        repr(urllib_exc.__cause__),
        repr(urllib_exc.__context__),
        urllib_formatted,
    ):
        lowered = surface.lower()
        assert FAKE_URL_TOKEN.lower() not in lowered
        assert FAKE_BASE_URL.lower() not in lowered
        assert FAKE_SECRET.lower() not in lowered


@pytest.mark.parametrize(
    ("secret_key", "base_url", "echo_builder"),
    [
        (
            FAKE_SECRET,
            FAKE_BASE_URL,
            lambda _k, _u: f"invalid tok {FAKE_URL_TOKEN.upper()}",
        ),
        (
            FAKE_SECRET,
            FAKE_BASE_URL,
            lambda _k, _u: "invalid tok SeCrEt-PrOxY-ToK-54321",
        ),
        (
            "Dummy-Key/Part+1=99",
            f"https://proxy.example.test/{FAKE_URL_TOKEN}/Sub+Seg",
            lambda k, _u: f"bad key {urllib.parse.quote(k, safe='').lower()}",
        ),
        (
            "Dummy-Key/Part+1=99",
            f"https://proxy.example.test/{FAKE_URL_TOKEN}/Sub+Seg",
            lambda _k, u: f"bad url {urllib.parse.quote(u, safe='').lower()}",
        ),
        (
            "Dummy-Key/Part+1=99",
            f"https://proxy.example.test/{FAKE_URL_TOKEN}/Sub+Seg",
            lambda _k, _u: f"bad seg {urllib.parse.quote('Sub+Seg', safe='').upper()}",
        ),
    ],
)
def test_401_redaction_is_case_insensitive_and_covers_url_encoded_forms(
    monkeypatch: pytest.MonkeyPatch,
    secret_key: str,
    base_url: str,
    echo_builder: object,
) -> None:
    assert callable(echo_builder)
    monkeypatch.setenv(API_KEY_ENV_VAR, secret_key)
    monkeypatch.setenv(BASE_URL_ENV_VAR, base_url)
    echoed = str(echo_builder(secret_key, base_url))

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=lambda url, headers, body, timeout: TransportResponse(
            status_code=401,
            body=json.dumps(
                {"type": "error", "error": {"type": "authentication_error", "message": echoed}}
            ).encode("utf-8"),
        ),
    )

    with pytest.raises(AnthropicAPIError) as exc_info:
        assistant.ask("hello", "rep-0")

    msg = str(exc_info.value)
    assert exc_info.value.status_code == 401
    assert "[REDACTED]" in msg
    lowered = msg.lower()
    for forbidden in (
        secret_key,
        urllib.parse.quote(secret_key, safe=""),
        base_url,
        urllib.parse.quote(base_url, safe=""),
        FAKE_URL_TOKEN,
        "sub+seg",
        urllib.parse.quote("Sub+Seg", safe=""),
    ):
        assert forbidden.lower() not in lowered
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_200_reply_text_echoing_secrets_is_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_key = "Dummy-Key/Echo+42"
    base_url = f"https://proxy.example.test/{FAKE_URL_TOKEN}/Extra+Seg"
    monkeypatch.setenv(API_KEY_ENV_VAR, secret_key)
    monkeypatch.setenv(BASE_URL_ENV_VAR, base_url)

    encoded_url = urllib.parse.quote(base_url, safe="").lower()
    encoded_seg = urllib.parse.quote("Extra+Seg", safe="").upper()
    encoded_key = urllib.parse.quote(secret_key, safe="").lower()

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=lambda url, headers, body, timeout: _ok_response(
            [
                {
                    "type": "text",
                    "text": (
                        f"ok: tok={FAKE_URL_TOKEN} upper={FAKE_URL_TOKEN.upper()} "
                        f"url={encoded_url} seg={encoded_seg} key={secret_key.upper()} "
                        f"enc_key={encoded_key}"
                    ),
                }
            ]
        ),
    )

    reply = assistant.ask("hello", "rep-0")
    assert reply.startswith("ok: ")
    assert "[REDACTED]" in reply
    lowered = reply.lower()
    for forbidden in (
        FAKE_URL_TOKEN,
        base_url,
        encoded_url,
        "extra+seg",
        encoded_seg,
        secret_key,
        encoded_key,
    ):
        assert forbidden.lower() not in lowered


@pytest.mark.parametrize(
    "invalid_base_url",
    [
        f"https://proxy.example.test:/{FAKE_URL_TOKEN}",
        f"https://proxy.example.test:0/{FAKE_URL_TOKEN}",
        f"http://localhost:/{FAKE_URL_TOKEN}",
        f"http://localhost:0/{FAKE_URL_TOKEN}",
        f"https://proxy.example.test./{FAKE_URL_TOKEN}",
        f"http://localhost./{FAKE_URL_TOKEN}",
        f"https://.proxy.example.test/{FAKE_URL_TOKEN}",
        f"https://proxy..example.test/{FAKE_URL_TOKEN}",
        f"https://.../{FAKE_URL_TOKEN}",
        f"https://./{FAKE_URL_TOKEN}",
        f"https://proxy.example.test\\{FAKE_URL_TOKEN}",
        f"https://proxy.example.test\\@evil.test/{FAKE_URL_TOKEN}",
        f"https://proxy.example.test\x00/{FAKE_URL_TOKEN}",
        f"https://proxy.example.test/{FAKE_URL_TOKEN}\r\n",
        f"https://proxy.example.test/{FAKE_URL_TOKEN}\x1b",
        f"https://proxy.example.test\x7f/{FAKE_URL_TOKEN}",
        f"https://proxy.example.test\x85/{FAKE_URL_TOKEN}",
        f"https://pr\u00f6xy.example.test/{FAKE_URL_TOKEN}",
        f"https://pr\u043exy.example.test/{FAKE_URL_TOKEN}",
        f"https://proxy\u200b.example.test/{FAKE_URL_TOKEN}",
        f"https://proxy\ufeff.example.test/{FAKE_URL_TOKEN}",
        f"https://user:pass@proxy.example.test/{FAKE_URL_TOKEN}",
        f"https://user@proxy.example.test/{FAKE_URL_TOKEN}",
        f"https://@proxy.example.test/{FAKE_URL_TOKEN}",
        f"https://proxy.example.test/{FAKE_URL_TOKEN}?a=1",
        f"https://proxy.example.test/{FAKE_URL_TOKEN}?",
        f"https://proxy.example.test/{FAKE_URL_TOKEN}#frag",
        f"https://proxy.example.test/{FAKE_URL_TOKEN}#",
        f"http://remote.example.test/{FAKE_URL_TOKEN}",
    ],
)
def test_validate_base_url_hardened_rejections(
    monkeypatch: pytest.MonkeyPatch,
    invalid_base_url: str,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    monkeypatch.setenv(BASE_URL_ENV_VAR, invalid_base_url)

    transport_called = False

    def spy_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        nonlocal transport_called
        del url, headers, body, timeout
        transport_called = True
        return _ok_response([{"type": "text", "text": "ok"}])

    assistant = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=spy_transport,
    )

    with pytest.raises(AnthropicAssistantError) as exc_info:
        assistant.ask("hello", "rep-0")

    assert not transport_called
    msg = str(exc_info.value)
    assert "proxy.example.test" not in msg
    assert "remote.example.test" not in msg
    assert "evil.test" not in msg
    assert "user" not in msg
    assert "frag" not in msg
    _assert_no_secrets_leaked(exc_info.value)
