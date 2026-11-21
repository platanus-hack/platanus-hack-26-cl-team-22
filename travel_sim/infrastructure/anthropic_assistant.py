"""Anthropic Messages API adapter implementing AssistantPort using stdlib urllib only."""
from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from travel_sim.application.ports import AssistantPort

API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"
BASE_URL_ENV_VAR = "ANTHROPIC_BASE_URL"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"
MESSAGES_PATH = "/v1/messages"

DEFAULT_MAX_TOKENS = 1024
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 0.5


class AnthropicAssistantError(RuntimeError):
    """Base error raised when an Anthropic Messages API call fails."""


class AnthropicTimeoutError(AnthropicAssistantError):
    """Raised when an Anthropic Messages API request times out."""


class AnthropicAPIError(AnthropicAssistantError):
    """Raised when the Anthropic Messages API returns a non-success HTTP status."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class TransportResponse:
    """HTTP response returned by an injectable Anthropic transport callable."""

    status_code: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)


AnthropicTransport = Callable[[str, Mapping[str, str], bytes, float], TransportResponse]


def _urllib_transport(
    url: str,
    headers: Mapping[str, str],
    body: bytes,
    timeout: float,
) -> TransportResponse:
    request = urllib.request.Request(
        url,
        data=body,
        headers=dict(headers),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            resp_headers = {k.lower(): v for k, v in response.headers.items()}
            return TransportResponse(
                status_code=int(response.status),
                body=response.read(),
                headers=resp_headers,
            )
    except urllib.error.HTTPError as exc:
        resp_headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        try:
            err_body = exc.read()
        except OSError:
            err_body = b""
        return TransportResponse(
            status_code=int(exc.code),
            body=err_body,
            headers=resp_headers,
        )


def _redact_secret(text: str, secret: str) -> str:
    if not secret:
        return text
    return text.replace(secret, "[REDACTED]")


def _extract_error_detail(body: bytes, api_key: str) -> str:
    if not body:
        return "empty response body"
    decoded = body.decode("utf-8", errors="replace").strip()
    if not decoded:
        return "empty response body"
    try:
        parsed: Any = json.loads(decoded)
    except json.JSONDecodeError:
        return _redact_secret(decoded[:200], api_key)

    if isinstance(parsed, dict):
        err_obj = parsed.get("error")
        if isinstance(err_obj, dict):
            err_type = err_obj.get("type")
            err_msg = err_obj.get("message")
            if isinstance(err_msg, str) and err_msg.strip():
                if isinstance(err_type, str) and err_type.strip():
                    return _redact_secret(f"{err_type.strip()}: {err_msg.strip()}", api_key)
                return _redact_secret(err_msg.strip(), api_key)
    return _redact_secret(decoded[:200], api_key)


def _extract_reply_text(body: bytes) -> str:
    try:
        decoded = body.decode("utf-8")
        parsed: Any = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnthropicAssistantError("Anthropic API returned invalid JSON response") from exc

    if not isinstance(parsed, dict):
        raise AnthropicAssistantError("Anthropic API response JSON root must be an object")

    content = parsed.get("content")
    if not isinstance(content, list):
        raise AnthropicAssistantError("Anthropic API response missing 'content' list")

    text_parts: list[str] = []
    for block in content:
        if (
            isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ):
            text_parts.append(block["text"])

    if not text_parts:
        raise AnthropicAssistantError("Anthropic API response contained no text content blocks")

    return "".join(text_parts)


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


class AnthropicAssistant(AssistantPort):
    """AssistantPort adapter calling the Anthropic Messages API via urllib."""

    def __init__(
        self,
        model: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: AnthropicTransport | None = None,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        sleep: Callable[[float], None] | None = None,
        anthropic_version: str = DEFAULT_ANTHROPIC_VERSION,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError(f"max_tokens must be an integer >= 1, got {max_tokens!r}")
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError(f"timeout must be a finite number > 0, got {timeout!r}")
        if transport is not None and not callable(transport):
            raise TypeError("transport must be callable or None")
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
            raise ValueError(f"max_retries must be an integer >= 0, got {max_retries!r}")
        if (
            isinstance(backoff_seconds, bool)
            or not isinstance(backoff_seconds, (int, float))
            or not math.isfinite(backoff_seconds)
            or backoff_seconds < 0
        ):
            raise ValueError(
                f"backoff_seconds must be a finite number >= 0, got {backoff_seconds!r}"
            )
        if sleep is not None and not callable(sleep):
            raise TypeError("sleep must be callable or None")
        if not isinstance(anthropic_version, str) or not anthropic_version.strip():
            raise ValueError("anthropic_version must be a non-empty string")

        self._model = model.strip()
        self._max_tokens = max_tokens
        self._timeout = float(timeout)
        self._transport: AnthropicTransport = (
            transport if transport is not None else _urllib_transport
        )
        self._max_retries = max_retries
        self._backoff_seconds = float(backoff_seconds)
        self._sleep: Callable[[float], None] = sleep if sleep is not None else time.sleep
        self._anthropic_version = anthropic_version.strip()

    @property
    def model(self) -> str:
        """Return the configured Anthropic model name."""
        return self._model

    @property
    def max_tokens(self) -> int:
        """Return the configured maximum output token count."""
        return self._max_tokens

    @property
    def timeout(self) -> float:
        """Return the configured HTTP request timeout in seconds."""
        return self._timeout

    @property
    def max_retries(self) -> int:
        """Return the configured maximum retry count for 429 and 5xx responses."""
        return self._max_retries

    @property
    def anthropic_version(self) -> str:
        """Return the configured anthropic-version header value."""
        return self._anthropic_version

    def __repr__(self) -> str:
        return (
            f"AnthropicAssistant(model={self._model!r}, "
            f"max_tokens={self._max_tokens!r}, timeout={self._timeout!r})"
        )

    def ask(self, prompt: str, salt: str) -> str:
        """Send prompt to the Anthropic Messages API and return concatenated text blocks."""
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("prompt must be a non-empty string")
        if not isinstance(salt, str):
            raise ValueError("salt must be a string")  # noqa: TRY004

        # Read credentials and endpoint strictly at call time; never store on self.
        api_key = os.environ.get(API_KEY_ENV_VAR, "").strip()
        if not api_key:
            raise AnthropicAssistantError(
                f"Missing {API_KEY_ENV_VAR} environment variable for Anthropic API request"
            )

        raw_base_url = os.environ.get(BASE_URL_ENV_VAR, "").strip()
        base_url = (raw_base_url or DEFAULT_ANTHROPIC_BASE_URL).rstrip("/")
        url = f"{base_url}{MESSAGES_PATH}"

        headers = {
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": self._anthropic_version,
        }
        payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        for attempt in range(self._max_retries + 1):
            response = self._dispatch_once(url, headers, body_bytes, api_key=api_key)
            if 200 <= response.status_code < 300:
                return _extract_reply_text(response.body)

            detail = _extract_error_detail(response.body, api_key)
            if _is_retryable_status(response.status_code) and attempt < self._max_retries:
                delay = self._backoff_seconds * (2**attempt)
                self._sleep(delay)
                continue

            raise AnthropicAPIError(
                response.status_code,
                f"Anthropic API request failed with HTTP {response.status_code}: {detail}",
            )

        raise AnthropicAssistantError("Anthropic API request failed after retries")  # pragma: no cover

    def _dispatch_once(
        self,
        url: str,
        headers: Mapping[str, str],
        body_bytes: bytes,
        *,
        api_key: str,
    ) -> TransportResponse:
        try:
            return self._transport(url, dict(headers), body_bytes, self._timeout)
        except urllib.error.HTTPError as exc:
            resp_headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
            try:
                err_body = exc.read()
            except OSError:
                err_body = b""
            return TransportResponse(
                status_code=int(exc.code),
                body=err_body,
                headers=resp_headers,
            )
        except TimeoutError:
            raise AnthropicTimeoutError(
                f"Anthropic API request timed out after {self._timeout}s"
            ) from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise AnthropicTimeoutError(
                    f"Anthropic API request timed out after {self._timeout}s"
                ) from None
            safe_reason = _redact_secret(str(exc.reason), api_key)
            raise AnthropicAssistantError(
                f"Anthropic API transport error: {safe_reason}"
            ) from None


__all__ = [
    "API_KEY_ENV_VAR",
    "BASE_URL_ENV_VAR",
    "DEFAULT_ANTHROPIC_BASE_URL",
    "DEFAULT_ANTHROPIC_VERSION",
    "DEFAULT_BACKOFF_SECONDS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TIMEOUT_SECONDS",
    "MESSAGES_PATH",
    "AnthropicAPIError",
    "AnthropicAssistant",
    "AnthropicAssistantError",
    "AnthropicTimeoutError",
    "AnthropicTransport",
    "TransportResponse",
]
