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
_HOST_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")


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
        ) from None

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
        ) from None

    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302


def _read_bounded(stream: Any, max_bytes: int = MAX_RESPONSE_BYTES) -> bytes:
    fallback_read = False
    try:
        chunk = stream.read(max_bytes + 1)
    except TypeError:
        fallback_read = True
    if fallback_read:
        chunk = stream.read()
    if len(chunk) > max_bytes:
        raise AnthropicAssistantError(
            f"Anthropic API response body exceeds {max_bytes} byte limit"
        ) from None
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
    http_error_response: TransportResponse | None = None
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
        status_code = int(exc.code)
        try:
            err_body = _read_bounded(exc, MAX_RESPONSE_BYTES)
        except AnthropicAssistantError:
            http_error_response = None
        except (OSError, http.client.HTTPException, ValueError):
            http_error_response = TransportResponse(
                status_code=status_code,
                body=b"",
                headers=resp_headers,
            )
        else:
            http_error_response = TransportResponse(
                status_code=status_code,
                body=err_body,
                headers=resp_headers,
            )
        finally:
            with contextlib.suppress(OSError, ValueError):
                exc.close()

    if http_error_response is not None:
        return http_error_response
    raise AnthropicAssistantError(
        f"Anthropic API response body exceeds {MAX_RESPONSE_BYTES} byte limit"
    ) from None


def _has_disallowed_url_char(value: str) -> bool:
    for ch in value:
        code = ord(ch)
        if ch.isspace() or ch == "\\" or code < 32 or code == 127:
            return True
        if unicodedata.category(ch).startswith("C"):
            return True
    return False


def _validate_base_url(raw_env_url: str | None) -> str:
    candidate = DEFAULT_ANTHROPIC_BASE_URL if not raw_env_url else raw_env_url

    if (
        not candidate
        or _has_disallowed_url_char(candidate)
        or "?" in candidate
        or "#" in candidate
    ):
        raise AnthropicAssistantError("Invalid Anthropic base URL configuration")

    parsed: urllib.parse.SplitResult | None = None
    port: int | None = None
    try:
        parsed = urllib.parse.urlsplit(candidate)
        port = parsed.port
    except ValueError:
        parsed = None

    if parsed is None:
        raise AnthropicAssistantError("Invalid Anthropic base URL configuration") from None

    scheme = parsed.scheme.lower()
    if scheme not in {"https", "http"}:
        raise AnthropicAssistantError(
            "Invalid Anthropic base URL scheme; only https is permitted"
        )

    netloc = parsed.netloc
    if not netloc or any(ord(ch) <= 32 or ord(ch) >= 127 for ch in netloc):
        raise AnthropicAssistantError("Invalid Anthropic base URL host")

    if (
        "@" in netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise AnthropicAssistantError("Invalid Anthropic base URL format")

    port_str: str | None = None
    if netloc.startswith("["):
        close_idx = netloc.find("]")
        if close_idx == -1:
            raise AnthropicAssistantError("Invalid Anthropic base URL host")
        host_part = netloc[1:close_idx]
        rest = netloc[close_idx + 1 :]
        if rest:
            if not rest.startswith(":"):
                raise AnthropicAssistantError("Invalid Anthropic base URL format")
            port_str = rest[1:]
    else:
        if "[" in netloc or "]" in netloc:
            raise AnthropicAssistantError("Invalid Anthropic base URL host")
        if ":" in netloc:
            host_part, _, port_str = netloc.partition(":")
            if ":" in port_str:
                raise AnthropicAssistantError("Invalid Anthropic base URL format")
        else:
            host_part = netloc

    if port_str is not None:
        if not port_str or not port_str.isascii() or not port_str.isdigit():
            raise AnthropicAssistantError("Invalid Anthropic base URL format")
        port_val = int(port_str)
        if port_val < 1 or port_val > 65535 or port != port_val:
            raise AnthropicAssistantError("Invalid Anthropic base URL format")
    elif port is not None:
        raise AnthropicAssistantError("Invalid Anthropic base URL format")

    hostname = (parsed.hostname or "").lower()
    if not host_part or not hostname:
        raise AnthropicAssistantError("Invalid Anthropic base URL host")

    if netloc.startswith("["):
        invalid_ipv6 = False
        try:
            ipaddress.IPv6Address(host_part)
        except ValueError:
            invalid_ipv6 = True
        if invalid_ipv6:
            raise AnthropicAssistantError("Invalid Anthropic base URL host") from None
    else:
        if (
            host_part.startswith(".")
            or host_part.endswith(".")
            or ".." in host_part
            or all(ch == "." for ch in host_part)
        ):
            raise AnthropicAssistantError("Invalid Anthropic base URL host")
        labels = host_part.split(".")
        if any(not _HOST_LABEL_RE.match(label) for label in labels):
            raise AnthropicAssistantError("Invalid Anthropic base URL host")

    if scheme == "http" and hostname not in _LOCAL_HTTP_HOSTS:
        raise AnthropicAssistantError(
            "Invalid Anthropic base URL: http is only permitted for localhost or 127.0.0.1"
        )

    return candidate.rstrip("/")


def _add_secret_variants(candidates: set[str], value: str) -> None:
    if not value:
        return
    base_forms = {value, value.lower(), value.upper()}
    unquoted = urllib.parse.unquote(value)
    if unquoted and unquoted.lower() not in _NON_SECRET_PATH_SEGMENTS:
        base_forms.update((unquoted, unquoted.lower(), unquoted.upper()))
    for form in base_forms:
        if not form:
            continue
        candidates.add(form)
        for encoded in (
            urllib.parse.quote(form, safe=""),
            urllib.parse.quote(form, safe=":/"),
            urllib.parse.quote_plus(form),
        ):
            if encoded:
                candidates.add(encoded)
                candidates.add(encoded.lower())
                candidates.add(encoded.upper())


def _collect_secrets(api_key: str, *urls: str) -> tuple[str, ...]:
    candidates: set[str] = set()
    if api_key:
        _add_secret_variants(candidates, api_key)
    for raw_url in urls:
        if not raw_url:
            continue
        stripped = raw_url.strip()
        if not stripped:
            continue
        _add_secret_variants(candidates, stripped)
        without_slash = stripped.rstrip("/")
        if without_slash:
            _add_secret_variants(candidates, without_slash)
        try:
            parsed = urllib.parse.urlsplit(without_slash)
        except ValueError:
            continue
        if parsed.scheme and parsed.netloc:
            _add_secret_variants(candidates, f"{parsed.scheme}://{parsed.netloc}")
        if parsed.netloc:
            _add_secret_variants(candidates, parsed.netloc)
        if parsed.hostname:
            _add_secret_variants(candidates, parsed.hostname)
        if parsed.username:
            _add_secret_variants(candidates, parsed.username)
        if parsed.password:
            _add_secret_variants(candidates, parsed.password)
        if parsed.query:
            _add_secret_variants(candidates, parsed.query)
        if parsed.fragment:
            _add_secret_variants(candidates, parsed.fragment)
        path = parsed.path
        if path and path != "/":
            _add_secret_variants(candidates, path)
            stripped_path = path.strip("/")
            if stripped_path and stripped_path.lower() not in _NON_SECRET_PATH_SEGMENTS:
                _add_secret_variants(candidates, stripped_path)
            for seg in path.split("/"):
                if seg and seg.lower() not in _NON_SECRET_PATH_SEGMENTS:
                    _add_secret_variants(candidates, seg)
    return tuple(sorted(candidates, key=len, reverse=True))


def _redact_secrets(text: str, secrets: Sequence[str]) -> str:
    if not text or not secrets:
        return text
    seen_lower: set[str] = set()
    ordered: list[str] = []
    for secret in sorted(secrets, key=len, reverse=True):
        if not secret:
            continue
        folded = secret.lower()
        if folded in seen_lower:
            continue
        seen_lower.add(folded)
        ordered.append(secret)
    if not ordered:
        return text
    pattern = re.compile("|".join(re.escape(secret) for secret in ordered), re.IGNORECASE)
    return pattern.sub("[REDACTED]", text)


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
    invalid_json = False
    parsed: Any = None
    try:
        decoded = body.decode("utf-8")
        parsed = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        invalid_json = True
    if invalid_json:
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
            return
        except TypeError:
            pass
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

        secrets = _collect_secrets(api_key, url, base_url)
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
                reply_text = _extract_reply_text(response.body)
                return _redact_secrets(reply_text, secrets)

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
        response: TransportResponse | None = None
        pending_error: AnthropicAssistantError | None = None
        try:
            response = self._transport(url, dict(headers), body_bytes, self._timeout)
        except urllib.error.HTTPError as exc:
            resp_headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
            status_code = int(exc.code)
            try:
                err_body = _read_bounded(exc, MAX_RESPONSE_BYTES)
            except AnthropicAssistantError:
                pending_error = AnthropicAssistantError(
                    f"Anthropic API response body exceeds {MAX_RESPONSE_BYTES} byte limit"
                )
            except (OSError, http.client.HTTPException, ValueError):
                response = TransportResponse(
                    status_code=status_code,
                    body=b"",
                    headers=resp_headers,
                )
            else:
                response = TransportResponse(
                    status_code=status_code,
                    body=err_body,
                    headers=resp_headers,
                )
            finally:
                with contextlib.suppress(OSError, ValueError):
                    exc.close()
        except TimeoutError:
            pending_error = AnthropicTimeoutError(
                f"Anthropic API request timed out after {self._timeout}s"
            )
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                pending_error = AnthropicTimeoutError(
                    f"Anthropic API request timed out after {self._timeout}s"
                )
            else:
                secrets = _collect_secrets(api_key, url, base_url)
                safe_reason = _redact_secrets(str(exc.reason), secrets)[:200]
                pending_error = AnthropicAssistantError(
                    f"Anthropic API transport error: {safe_reason}"
                )
        except AnthropicAssistantError as exc:
            exc.__cause__ = None
            exc.__context__ = None
            pending_error = exc
        except (http.client.HTTPException, ValueError, OSError) as exc:
            pending_error = AnthropicAssistantError(
                f"Anthropic API transport error ({type(exc).__name__})"
            )

        if pending_error is not None:
            raise pending_error from None
        if response is None:  # pragma: no cover - defensive
            raise AnthropicAssistantError("Anthropic API transport returned no response") from None

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
