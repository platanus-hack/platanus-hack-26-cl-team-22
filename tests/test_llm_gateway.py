import asyncio

import pytest

from core.llm_gateway import BudgetExceeded, LLMGateway, validate

ACTIONS = {"mover": {"dir"}, "esperar": set()}


def test_validate_accepts_catalog_actions_only():
    assert validate('{"accion":"esperar","args":{}}', ACTIONS)
    assert validate('{"accion":"mover","args":{"dir":"n"}}', ACTIONS)
    assert validate('{"accion":"volar","args":{}}', ACTIONS) is None
    assert validate('{"accion":"mover","args":{}}', ACTIONS) is None  # wrong args
    assert validate("garbage", ACTIONS) is None


def test_record_then_replay_makes_zero_calls(tmp_path):
    log = str(tmp_path / "log.jsonl")

    async def fake(prompt: str) -> str:
        return '{"accion":"esperar","args":{}}'

    rec = LLMGateway(fake, log)
    out = asyncio.run(rec.ask("hola", salt="a|1"))
    assert rec.calls == 1

    rep = LLMGateway(fake, log, mode="replay")
    assert asyncio.run(rep.ask("hola", salt="a|1")) == out
    assert rep.calls == 0
    with pytest.raises(KeyError):
        asyncio.run(rep.ask("otra cosa", salt="a|2"))


def test_call_budget_stops_the_run(tmp_path):
    async def fake(prompt: str) -> str:
        return "{}"

    gw = LLMGateway(fake, str(tmp_path / "l.jsonl"), max_calls=1)
    asyncio.run(gw.ask("uno"))
    with pytest.raises(BudgetExceeded):
        asyncio.run(gw.ask("dos"))
