"""Tests for the urllib-based AnthropicAssistant adapter."""
from __future__ import annotations

import json
import urllib.error
from collections.abc import Mapping

import pytest

from travel_sim.application.ports import AssistantPort
from travel_sim.infrastructure.anthropic_assistant import (
    API_KEY_ENV_VAR,
    BASE_URL_ENV_VAR,
    AnthropicAPIError,
    AnthropicAssistant,
    AnthropicAssistantError,
    AnthropicTimeoutError,
    TransportResponse,
)

FAKE_SECRET = "dummy-test-token-value-98765"


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


def test_secret_never_appears_in_repr_vars_or_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)

    def bad_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        del url, headers, body, timeout
        return TransportResponse(
            status_code=401,
            body=json.dumps(
                {
                    "type": "error",
                    "error": {
                        "type": "authentication_error",
                        "message": f"Invalid key {FAKE_SECRET}",
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

    assert FAKE_SECRET not in repr(assistant)
    assert FAKE_SECRET not in str(assistant)
    assert FAKE_SECRET not in repr(vars(assistant))

    with pytest.raises(AnthropicAPIError) as exc_info:
        assistant.ask("hello", "rep-0")

    assert exc_info.value.status_code == 401
    assert FAKE_SECRET not in str(exc_info.value)
    assert FAKE_SECRET not in repr(exc_info.value)


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
    sleeps: list[float] = []
    attempts = 0

    def always_429(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> TransportResponse:
        nonlocal attempts
        del url, headers, body, timeout
        attempts += 1
        return TransportResponse(
            status_code=429,
            body=json.dumps({"error": {"message": "too many requests"}}).encode("utf-8"),
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
    assert FAKE_SECRET not in str(exc_info.value)


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
    assert FAKE_SECRET not in str(exc_info.value)


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
        AnthropicAssistant("claude-sonnet-4-20250514", max_retries=-1)

    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_SECRET)
    empty_content = AnthropicAssistant(
        "claude-sonnet-4-20250514",
        transport=lambda url, headers, body, timeout: _ok_response(
            [{"type": "thinking", "thinking": "no text block"}]
        ),
    )
    with pytest.raises(AnthropicAssistantError, match="no text content blocks"):
        empty_content.ask("prompt", "rep-0")
