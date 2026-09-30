"""Shared tool loop: limits, repeat handling, untrusted framing, events, abort."""

import asyncio

import pytest

from backend.tools import executor
from backend.tools.executor import ToolLimits, extract_sources, run_tool_loop


def call(name="web_search", args='{"query": "x"}', cid="c1"):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": args}}


class FakeModel:
    """Replays scripted responses and records the tools/messages of every query."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.seen = []

    async def __call__(self, model, messages, tools=None):
        self.seen.append({"tools": tools, "messages": list(messages)})
        return self.responses.pop(0) if self.responses else {"content": "done"}


@pytest.fixture
def fake_tool(monkeypatch):
    calls = []

    async def execute(name, args, target_workspace=None):
        calls.append((name, args, target_workspace))
        return "1. [Doc](https://example.com/a)\n   see https://example.com/b."

    monkeypatch.setattr(executor, "execute_tool", execute)
    return calls


def run(coro):
    return asyncio.run(coro)


def test_tool_round_then_final_answer(fake_tool):
    model = FakeModel([
        {"content": "", "tool_calls": [call()], "usage": {"total_tokens": 10}},
        {"content": "final", "usage": {"total_tokens": 5}, "cost": {"total_cost": 0.5}},
    ])
    res = run(run_tool_loop(model, "m", [{"role": "user", "content": "q"}], [{"t": 1}],
                            target_workspace="ws"))
    assert res["content"] == "final" and res["stop_reason"] == "final"
    assert res["usage"]["total_tokens"] == 15 and res["cost"]["total_cost"] == 0.5
    assert res["sources"] == ["https://example.com/a", "https://example.com/b"]
    assert fake_tool == [("web_search", {"query": "x"}, "ws")]  # workspace reaches the tool
    tool_msg = res["messages"][-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c1"
    assert "untrusted external data" in tool_msg["content"]
    assert res["tools_executed"][0]["ok"] is True


def test_missing_call_id_is_generated(fake_tool):
    tc = {"function": {"name": "web_search", "arguments": "{}"}}
    model = FakeModel([{"tool_calls": [tc]}, {"content": "ok"}])
    res = run(run_tool_loop(model, "m", [], [{}]))
    assistant = next(m for m in res["messages"] if m.get("tool_calls"))
    tool = next(m for m in res["messages"] if m["role"] == "tool")
    assert assistant["tool_calls"][0]["id"] == tool["tool_call_id"]


def test_call_budget_forces_toolless_final_turn(fake_tool):
    model = FakeModel([
        {"tool_calls": [call(args=f'{{"query": "q{i}"}}', cid=f"c{i}")]} for i in range(2)
    ] + [{"content": "wrapped up"}])
    res = run(run_tool_loop(model, "m", [], [{}], limits=ToolLimits(max_calls=2)))
    assert len(fake_tool) == 2
    assert res["stop_reason"] == "max_calls" and res["content"] == "wrapped up"
    last = model.seen[-1]
    assert last["tools"] is None
    assert "Tool budget" in last["messages"][-1]["content"]


def test_turn_limit(fake_tool):
    model = FakeModel([{"tool_calls": [call(args=f'{{"query": "{i}"}}', cid=f"c{i}")]} for i in range(9)]
                      + [{"content": "x"}])
    res = run(run_tool_loop(model, "m", [], [{}], limits=ToolLimits(max_turns=2)))
    assert res["stop_reason"] == "max_turns"
    assert model.seen[-1]["tools"] is None


def test_identical_calls_hit_cache_and_get_warned(fake_tool):
    model = FakeModel([
        {"tool_calls": [call(cid="a")]},
        {"tool_calls": [call(cid="b")]},
        {"tool_calls": [call(cid="c")]},
        {"content": "ok"},
    ])
    res = run(run_tool_loop(model, "m", [], [{}]))
    assert len(fake_tool) == 1  # executed once, repeats served from cache
    tool_msgs = [m for m in res["messages"] if m["role"] == "tool"]
    assert "do not repeat" in tool_msgs[-1]["content"]


def test_bad_json_arguments_reported_not_executed(fake_tool):
    model = FakeModel([{"tool_calls": [call(args="{not json")]}, {"content": "ok"}])
    res = run(run_tool_loop(model, "m", [], [{}]))
    assert fake_tool == []
    assert res["tools_executed"][0]["ok"] is False
    assert "not valid JSON" in res["messages"][-1]["content"]


def test_tool_timeout_and_exception_become_error_results(monkeypatch):
    async def slow(name, args, target_workspace=None):
        await asyncio.sleep(5)

    monkeypatch.setattr(executor, "execute_tool", slow)
    model = FakeModel([{"tool_calls": [call()]}, {"content": "ok"}])
    res = run(run_tool_loop(model, "m", [], [{}], limits=ToolLimits(tool_timeout_s=0.05)))
    assert res["tools_executed"][0]["ok"] is False
    assert "timed out" in res["tools_executed"][0]["result_preview"]

    async def boom(name, args, target_workspace=None):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(executor, "execute_tool", boom)
    model = FakeModel([{"tool_calls": [call()]}, {"content": "ok"}])
    res = run(run_tool_loop(model, "m", [], [{}]))
    assert "secret internal detail" not in res["tools_executed"][0]["result_preview"]


def test_abort_stops_before_querying(fake_tool):
    model = FakeModel([{"content": "never"}])
    res = run(run_tool_loop(model, "m", [], [{}], should_abort=lambda: True))
    assert res["stop_reason"] == "aborted" and model.seen == [] and res["content"] == ""


def test_events_in_order_and_callback_errors_do_not_break_loop(fake_tool):
    events = []

    async def on_event(e):
        events.append(e["type"])
        raise ValueError("ui went away")

    model = FakeModel([{"tool_calls": [call()]}, {"content": "ok"}])
    res = run(run_tool_loop(model, "m", [], [{}], on_event=on_event))
    assert events == ["tool_call", "tool_result"] and res["content"] == "ok"


def test_no_response_reported(fake_tool):
    async def dead(model, messages, tools=None):
        return None

    res = run(run_tool_loop(dead, "m", [], [{}]))
    assert res["stop_reason"] == "no_response"


def test_oversized_output_truncated(monkeypatch):
    async def big(name, args, target_workspace=None):
        return "x" * 50000

    monkeypatch.setattr(executor, "execute_tool", big)
    model = FakeModel([{"tool_calls": [call()]}, {"content": "ok"}])
    res = run(run_tool_loop(model, "m", [], [{}]))
    assert len(res["messages"][-2]["content"]) < executor.MAX_TOOL_OUTPUT_CHARS + 500


def test_extract_sources_strips_punctuation_and_dedupes():
    text = "see (https://a.com/x), https://a.com/x. and https://b.org/y;"
    assert extract_sources(text) == ["https://a.com/x", "https://b.org/y"]
