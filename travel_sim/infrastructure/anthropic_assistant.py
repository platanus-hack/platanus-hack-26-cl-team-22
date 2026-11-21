"""Anthropic Messages API adapter implementing AssistantPort using stdlib urllib only."""
from __future__ import annotations

import contextlib
import http.client
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
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

MAX_TIMEOUT_SECONDS = 120.0
MAX_RETRIES_LIMIT = 5
MAX_BACKOFF_SECONDS = 30.0
MAX_RESPONSE_BYTES = 1024 * 1024

_NON_SECRET_PATH_SEGMENTS = frozenset({"api", "v1", "v2", "messages"})
_LOCAL_HTTP_HOSTS = frozenset({"localhost", "127.0.0.1"})


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


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that refuses all HTTP redirects to protect credentials."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        del req, msg, headers, newurl
        if fp is not None:
            with contextlib.suppress(OSError, ValueError):
                fp.close()
        raise AnthropicAssistantError(
            f"Anthropic API HTTP redirect (status {code}) is disabled"
        )

    def http_error_302(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
    ) -> Any:
        del req, msg, headers
        if fp is not None:
            with contextlib.suppress(OSError, ValueError):
                fp.close()
        raise AnthropicAssistantError(
            f"Anthropic API HTTP redirect (status {code}) is disabled"
        )

    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302


def _read_bounded(stream: Any, max_bytes: int = MAX_RESPONSE_BYTES) -> bytes:
    try:
        chunk = stream.read(max_bytes + 1)
    except TypeError:
        chunk = stream.read()
    if len(chunk) > max_bytes:
        raise AnthropicAssistantError(
            f"Anthropic API response body exceeds {max_bytes} byte limit"
        )
    return chunk


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
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            resp_headers = {k.lower(): v for k, v in response.headers.items()}
            return TransportResponse(
                status_code=int(response.status),
                body=_read_bounded(response, MAX_RESPONSE_BYTES),
                headers=resp_headers,
            )
    except urllib.error.HTTPError as exc:
        resp_headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        try:
            err_body = _read_bounded(exc, MAX_RESPONSE_BYTES)
        except (OSError, http.client.HTTPException, ValueError):
            err_body = b""
        finally:
            with contextlib.suppress(OSError, ValueError):
                exc.close()
        return TransportResponse(
            status_code=int(exc.code),
            body=err_body,
            headers=resp_headers,
        )


def _validate_base_url(raw_env_url: str | None) -> str:
    candidate = DEFAULT_ANTHROPIC_BASE_URL if not raw_env_url else raw_env_url

    if (
        not candidate
        or any(ch.isspace() for ch in candidate)
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in candidate)
    ):
        raise AnthropicAssistantError("Invalid Anthropic base URL configuration")

    try:
        parsed = urllib.parse.urlsplit(candidate)
        _ = parsed.port
    except ValueError:
        raise AnthropicAssistantError("Invalid Anthropic base URL configuration") from None

    scheme = parsed.scheme.lower()
    if scheme not in {"https", "http"}:
        raise AnthropicAssistantError(
            "Invalid Anthropic base URL scheme; only https is permitted"
        )

    hostname = (parsed.hostname or "").lower()
    if not hostname or not parsed.netloc:
        raise AnthropicAssistantError("Invalid Anthropic base URL host")

    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise AnthropicAssistantError("Invalid Anthropic base URL format")

    if scheme == "http" and hostname not in _LOCAL_HTTP_HOSTS:
        raise AnthropicAssistantError(
            "Invalid Anthropic base URL: http is only permitted for localhost or 127.0.0.1"
        )

    return candidate.rstrip("/")


def _collect_secrets(api_key: str, *urls: str) -> tuple[str, ...]:
    candidates: set[str] = set()
    if api_key:
        candidates.add(api_key)
    for raw_url in urls:
        if not raw_url:
            continue
        stripped = raw_url.strip()
        if not stripped:
            continue
        candidates.add(stripped)
        without_slash = stripped.rstrip("/")
        if without_slash:
            candidates.add(without_slash)
        try:
            parsed = urllib.parse.urlsplit(without_slash)
        except ValueError:
            continue
        if parsed.scheme and parsed.netloc:
            candidates.add(f"{parsed.scheme}://{parsed.netloc}")
        if parsed.netloc:
            candidates.add(parsed.netloc)
        if parsed.hostname:
            candidates.add(parsed.hostname)
        if parsed.username:
            candidates.add(parsed.username)
        if parsed.password:
            candidates.add(parsed.password)
        if parsed.query:
            candidates.add(parsed.query)
        if parsed.fragment:
            candidates.add(parsed.fragment)
        path = parsed.path
        if path and path != "/":
            candidates.add(path)
            stripped_path = path.strip("/")
            if stripped_path and stripped_path.lower() not in _NON_SECRET_PATH_SEGMENTS:
                candidates.add(stripped_path)
            for seg in path.split("/"):
                if seg and seg.lower() not in _NON_SECRET_PATH_SEGMENTS:
                    candidates.add(seg)
    return tuple(sorted(candidates, key=len, reverse=True))


def _redact_secrets(text: str, secrets: Sequence[str]) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _redact_secret(text: str, secret: str, *extra_secrets: str) -> str:
    return _redact_secrets(text, _collect_secrets(secret, *extra_secrets))


def _extract_error_detail(body: bytes, api_key: str, *urls: str) -> str:
    if not body:
        return "empty response body"
    decoded = body.decode("utf-8", errors="replace").strip()
    if not decoded:
        return "empty response body"
    secrets = _collect_secrets(api_key, *urls)
    try:
        parsed: Any = json.loads(decoded)
    except json.JSONDecodeError:
        return _redact_secrets(decoded, secrets)[:200]

    if isinstance(parsed, dict):
        err_obj = parsed.get("error")
        if isinstance(err_obj, dict):
            err_type = err_obj.get("type")
            err_msg = err_obj.get("message")
            if isinstance(err_msg, str) and err_msg.strip():
                if isinstance(err_type, str) and err_type.strip():
                    detail = f"{err_type.strip()}: {err_msg.strip()}"
                else:
                    detail = err_msg.strip()
                return _redact_secrets(detail, secrets)[:200]
    return _redact_secrets(decoded, secrets)[:200]


def _extract_reply_text(body: bytes) -> str:
    try:
        decoded = body.decode("utf-8")
        parsed: Any = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AnthropicAssistantError("Anthropic API returned invalid JSON response") from None

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


def _validate_call_budget(call_budget: Any) -> None:
    if call_budget is None:
        return
    if callable(call_budget) or callable(getattr(call_budget, "consume", None)):
        return
    raise TypeError("call_budget must be callable, have a consume() method, or be None")


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
        call_budget: Callable[..., None] | Any | None = None,
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
            or timeout > MAX_TIMEOUT_SECONDS
        ):
            raise ValueError(
                f"timeout must be a finite number in (0, {MAX_TIMEOUT_SECONDS}], got {timeout!r}"
            )
        if transport is not None and not callable(transport):
            raise TypeError("transport must be callable or None")
        if (
            isinstance(max_retries, bool)
            or not isinstance(max_retries, int)
            or max_retries < 0
            or max_retries > MAX_RETRIES_LIMIT
        ):
            raise ValueError(
                f"max_retries must be an integer in [0, {MAX_RETRIES_LIMIT}], got {max_retries!r}"
            )
        if (
            isinstance(backoff_seconds, bool)
            or not isinstance(backoff_seconds, (int, float))
            or not math.isfinite(backoff_seconds)
            or backoff_seconds < 0
            or backoff_seconds > MAX_BACKOFF_SECONDS
        ):
            raise ValueError(
                f"backoff_seconds must be a finite number in [0, {MAX_BACKOFF_SECONDS}], "
                f"got {backoff_seconds!r}"
            )
        if sleep is not None and not callable(sleep):
            raise TypeError("sleep must be callable or None")
        if not isinstance(anthropic_version, str) or not anthropic_version.strip():
            raise ValueError("anthropic_version must be a non-empty string")
        _validate_call_budget(call_budget)

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
        self._call_budget = call_budget

    def bind_call_budget(self, call_budget: Callable[..., None] | Any | None) -> None:
        """Bind or replace the call budget tracker enforcing per-HTTP-attempt limits."""
        _validate_call_budget(call_budget)
        self._call_budget = call_budget

    def _consume_budget(self, salt: str) -> None:
        if self._call_budget is None:
            return
        consume_fn = getattr(self._call_budget, "consume", None)
        target = consume_fn if callable(consume_fn) else self._call_budget
        try:
            target(salt)
        except TypeError:
            target()

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

        raw_env_url = os.environ.get(BASE_URL_ENV_VAR)
        base_url = _validate_base_url(raw_env_url)
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
            self._consume_budget(salt)
            response = self._dispatch_once(
                url,
                headers,
                body_bytes,
                api_key=api_key,
                base_url=base_url,
            )
            if 200 <= response.status_code < 300:
                return _extract_reply_text(response.body)

            detail = _extract_error_detail(response.body, api_key, url, base_url)
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
        base_url: str = "",
    ) -> TransportResponse:
        try:
            response = self._transport(url, dict(headers), body_bytes, self._timeout)
        except urllib.error.HTTPError as exc:
            resp_headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
            try:
                err_body = _read_bounded(exc, MAX_RESPONSE_BYTES)
            except (OSError, http.client.HTTPException, ValueError):
                err_body = b""
            finally:
                with contextlib.suppress(OSError, ValueError):
                    exc.close()
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
            secrets = _collect_secrets(api_key, url, base_url)
            safe_reason = _redact_secrets(str(exc.reason), secrets)[:200]
            raise AnthropicAssistantError(
                f"Anthropic API transport error: {safe_reason}"
            ) from None
        except AnthropicAssistantError:
            raise
        except (http.client.HTTPException, ValueError, OSError) as exc:
            raise AnthropicAssistantError(
                f"Anthropic API transport error ({type(exc).__name__})"
            ) from None

        if len(response.body) > MAX_RESPONSE_BYTES:
            raise AnthropicAssistantError(
                f"Anthropic API response body exceeds {MAX_RESPONSE_BYTES} byte limit"
            )
        return response


__all__ = [
    "API_KEY_ENV_VAR",
    "BASE_URL_ENV_VAR",
    "DEFAULT_ANTHROPIC_BASE_URL",
    "DEFAULT_ANTHROPIC_VERSION",
    "DEFAULT_BACKOFF_SECONDS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_BACKOFF_SECONDS",
    "MAX_RESPONSE_BYTES",
    "MAX_RETRIES_LIMIT",
    "MAX_TIMEOUT_SECONDS",
    "MESSAGES_PATH",
    "AnthropicAPIError",
    "AnthropicAssistant",
    "AnthropicAssistantError",
    "AnthropicTimeoutError",
    "AnthropicTransport",
    "TransportResponse",
]
