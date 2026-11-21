"""JSONL record/replay adapter implementing AssistantPort without network calls."""
from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path

from travel_sim.application.ports import AssistantPort


class ReplayMode(str, Enum):
    """Operating modes for ReplayAssistant."""

    RECORD = "record"
    REPLAY = "replay"


class ReplayMissError(KeyError):
    """Raised in replay mode when the requested (salt, prompt) key is not recorded."""


class BudgetExceededError(RuntimeError):
    """Raised when an assistant call would exceed the configured call budget cap."""


def compute_cache_key(prompt: str, salt: str) -> str:
    """Compute a deterministic SHA-256 hex digest keyed by salt and prompt."""
    canonical = json.dumps({"salt": salt, "prompt": prompt}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ReplayAssistant(AssistantPort):
    """JSONL record/replay adapter for AssistantPort with call budget cap."""

    def __init__(
        self,
        store_path: str | Path,
        *,
        mode: ReplayMode | str = ReplayMode.REPLAY,
        assistant: AssistantPort | None = None,
        max_calls: int | None = None,
    ) -> None:
        self._path = Path(store_path)
        try:
            self._mode = mode if isinstance(mode, ReplayMode) else ReplayMode(str(mode))
        except ValueError as exc:
            raise ValueError(f"Invalid ReplayMode: {mode!r}") from exc

        if self._mode == ReplayMode.RECORD and assistant is None:
            raise ValueError("assistant must be provided when mode is 'record'")

        if max_calls is not None and (
            isinstance(max_calls, bool) or not isinstance(max_calls, int) or max_calls < 0
        ):
            raise ValueError(f"max_calls must be a non-negative int or None, got {max_calls!r}")

        self._assistant = assistant
        self._max_calls = max_calls
        self._calls_made = 0
        self._replay_hits = 0
        self._records: dict[str, str] = {}

        if self._path.is_file():
            self._load_existing()

    @property
    def store_path(self) -> Path:
        """Return the JSONL fixture file path."""
        return self._path

    @property
    def mode(self) -> ReplayMode:
        """Return the configured operating mode."""
        return self._mode

    @property
    def max_calls(self) -> int | None:
        """Return the configured call budget cap, or None if unlimited."""
        return self._max_calls

    @property
    def calls_made(self) -> int:
        """Return the number of calls made to the underlying assistant."""
        return self._calls_made

    @property
    def replay_hits(self) -> int:
        """Return the number of replies served from the JSONL cache."""
        return self._replay_hits

    @property
    def recorded_count(self) -> int:
        """Return the number of unique cached keys loaded or recorded."""
        return len(self._records)

    def _load_existing(self) -> None:
        with self._path.open("r", encoding="utf-8") as handle:
            for line_num, raw_line in enumerate(handle, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSONL entry on line {line_num} of {self._path}: {exc}"
                    ) from exc
                if not isinstance(entry, dict):
                    raise ValueError(  # noqa: TRY004
                        f"JSONL entry on line {line_num} of {self._path} must be an object"
                    )
                key = entry.get("key")
                reply = entry.get("reply")
                if not isinstance(key, str) or not isinstance(reply, str):
                    raise ValueError(  # noqa: TRY004
                        f"JSONL entry on line {line_num} of {self._path} "
                        "must contain string 'key' and 'reply'"
                    )
                self._records[key] = reply

    def _append_record(self, key: str, salt: str, prompt: str, reply: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "key": key,
            "salt": salt,
            "prompt": prompt,
            "reply": reply,
        }
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()

    def ask(self, prompt: str, salt: str) -> str:
        """Return a recorded reply in replay mode, or call and record in record mode."""
        key = compute_cache_key(prompt, salt)

        if self._mode == ReplayMode.REPLAY:
            if key not in self._records:
                raise ReplayMissError(
                    f"Replay cache miss for key {key} (salt={salt!r}) in {self._path}"
                )
            self._replay_hits += 1
            return self._records[key]

        if key in self._records:
            self._replay_hits += 1
            return self._records[key]

        if self._max_calls is not None and self._calls_made >= self._max_calls:
            raise BudgetExceededError(
                f"Call budget cap of {self._max_calls} reached; refusing call for salt={salt!r}"
            )

        assert self._assistant is not None
        self._calls_made += 1
        reply = self._assistant.ask(prompt, salt)
        self._records[key] = reply
        self._append_record(key, salt, prompt, reply)
        return reply


__all__ = [
    "BudgetExceededError",
    "ReplayAssistant",
    "ReplayMissError",
    "ReplayMode",
    "compute_cache_key",
]
