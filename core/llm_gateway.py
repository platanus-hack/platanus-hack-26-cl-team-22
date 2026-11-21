"""Single entry point for LLM calls: concurrency limit, call budget, JSONL record/replay.

Use only if the chosen idea needs LLM agents (see .claude/skills/llm-agents-sim).
The LLM proposes an action as JSON; the engine validates it against a closed catalog.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import Awaitable, Callable


def validate(raw: str, actions: dict[str, set[str]]) -> dict | None:
    """Return the parsed action, or None if it is not in the closed catalog."""
    try:
        a = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(a, dict) or a.get("accion") not in actions:
        return None
    if set(a.get("args", {})) != actions[a["accion"]]:
        return None
    return a


class BudgetExceeded(RuntimeError):
    pass


class LLMGateway:
    def __init__(
        self,
        call: Callable[[str], Awaitable[str]],
        log_path: str,
        mode: str = "record",
        max_concurrency: int = 8,
        max_calls: int | None = None,
    ):
        self.call, self.mode, self.log_path, self.max_calls = call, mode, log_path, max_calls
        self.sem, self.cache, self.calls = asyncio.Semaphore(max_concurrency), {}, 0
        if os.path.exists(log_path):
            with open(log_path) as f:
                for line in f:
                    r = json.loads(line)
                    self.cache[r["k"]] = r["out"]

    async def ask(self, prompt: str, salt: str = "") -> str:
        k = hashlib.sha256(f"{salt}|{prompt}".encode()).hexdigest()[:16]
        if k in self.cache:
            return self.cache[k]
        if self.mode == "replay":
            raise KeyError(f"response not recorded: {k}")
        if self.max_calls is not None and self.calls >= self.max_calls:
            raise BudgetExceeded(f"call budget of {self.max_calls} reached")
        async with self.sem:
            out = await self.call(prompt)
            self.calls += 1
        self.cache[k] = out
        self._append(k, out)
        return out

    def _append(self, k: str, out: str) -> None:
        # Tiny synchronous append: atomic enough between awaits in a single event loop.
        with open(self.log_path, "a") as f:
            f.write(json.dumps({"k": k, "out": out}) + "\n")
