"""MCP client: default-deny policy, secret redaction, stdio gate, real stdio server, approvals."""

import asyncio
import os
import sys

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.tools import executor, mcp_client
from backend.tools.executor import run_tool_loop

client = TestClient(app)
ECHO_SERVER = os.path.join(os.path.dirname(__file__), "fixtures", "echo_mcp_server.py")
SECRET = "hdr-secret-leaktest-0123456789"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_store(monkeypatch):
    for rec in mcp_client.list_servers():
        mcp_client.delete_server(rec["id"])
    monkeypatch.setenv("MCP_ALLOW_STDIO", "1")
    yield
    for rec in mcp_client.list_servers():
        mcp_client.delete_server(rec["id"])


@pytest.fixture
def echo():
    mcp_client.add_server({
        "id": "echo", "transport": "stdio", "command": sys.executable, "args": [ECHO_SERVER],
        "env": {"ECHO_TOKEN": SECRET},
    })
    rec = run(mcp_client.refresh_server("echo"))
    assert rec["last_error"] is None, rec
    return rec


def test_stdio_refused_unless_enabled(monkeypatch):
    monkeypatch.delenv("MCP_ALLOW_STDIO")
    with pytest.raises(mcp_client.McpError):
        mcp_client.add_server({"id": "x", "transport": "stdio", "command": "ls", "args": []})
    resp = client.post("/api/mcp-servers", json={"id": "x", "transport": "stdio", "command": "ls"})
    assert resp.status_code == 422


@pytest.mark.parametrize("bad", [
    {"id": "Bad Id", "transport": "http", "url": "http://x"},
    {"id": "a", "transport": "http", "url": "file:///etc/passwd"},
    {"id": "a", "transport": "ftp"},
    {"id": "a", "transport": "http", "url": "http://x", "headers": {"bad header": "v"}},
])
def test_invalid_servers_rejected(bad):
    with pytest.raises(mcp_client.McpError):
        mcp_client.add_server(bad)


def test_secrets_never_returned_and_merge_semantics():
    mcp_client.add_server({"id": "h", "transport": "http", "url": "http://localhost:1/mcp",
                           "headers": {"Authorization": f"Bearer {SECRET}"}})
    listed = client.get("/api/mcp-servers")
    assert listed.status_code == 200
    assert SECRET not in listed.text
    assert listed.json()["servers"][0]["headers_set"] == ["Authorization"]
    # Patching other fields keeps the stored header; an empty value deletes it.
    mcp_client.update_server("h", {"name": "renamed"})
    assert mcp_client.list_servers()[0]["headers_set"] == ["Authorization"]
    mcp_client.update_server("h", {"headers": {"Authorization": ""}})
    assert mcp_client.list_servers()[0]["headers_set"] == []


def test_discovered_tools_default_to_deny(echo):
    assert {t["name"]: t["policy"] for t in echo["tools"]} == {"echo": "deny", "boom": "deny"}
    assert mcp_client.get_tool_definitions() == []
    assert mcp_client.policy_for("mcp__echo__echo") == "deny"
    out = run(mcp_client.call_tool("mcp__echo__echo", {"text": "hi"}))
    assert out.startswith("Error")


def test_policy_is_preserved_on_refresh_and_exposes_tool(echo):
    mcp_client.update_server("echo", {"tool_policies": {"echo": "auto"}})
    run(mcp_client.refresh_server("echo"))
    defs = mcp_client.get_tool_definitions()
    assert [d["function"]["name"] for d in defs] == ["mcp__echo__echo"]
    assert defs[0]["function"]["description"].startswith("[MCP server echo]")
    assert run(mcp_client.call_tool("mcp__echo__echo", {"text": "hi"})) == "echo:hi"
    # The other tool stayed denied; disabling the server denies everything.
    assert mcp_client.policy_for("mcp__echo__boom") == "deny"
    mcp_client.update_server("echo", {"enabled": False})
    assert mcp_client.policy_for("mcp__echo__echo") == "deny"
    assert mcp_client.get_tool_definitions() == []


def test_server_side_error_is_reported_as_error(echo):
    mcp_client.update_server("echo", {"tool_policies": {"boom": "auto"}})
    out = run(mcp_client.call_tool("mcp__echo__boom", {}))
    # The SDK hides the server-side exception text; only the failure itself reaches the model.
    assert out.startswith("Error") and "boom" in out


def test_unknown_policy_and_tool_rejected(echo):
    with pytest.raises(mcp_client.McpError):
        mcp_client.update_server("echo", {"tool_policies": {"echo": "yes"}})
    with pytest.raises(mcp_client.McpError):
        mcp_client.update_server("echo", {"tool_policies": {"ghost": "auto"}})


def test_failed_refresh_keeps_old_tools(echo):
    mcp_client.update_server("echo", {"args": ["/nonexistent.py"]})
    rec = run(mcp_client.refresh_server("echo"))
    assert rec["last_error"]
    assert len(rec["tools"]) == 2


def test_api_roundtrip(echo):
    resp = client.put("/api/mcp-servers/echo", json={"tool_policies": {"echo": "ask"}})
    assert resp.status_code == 200
    assert {t["name"]: t["policy"] for t in resp.json()["server"]["tools"]}["echo"] == "ask"
    assert client.put("/api/mcp-servers/nope", json={"enabled": True}).status_code == 422
    assert client.delete("/api/mcp-servers/echo").status_code == 200
    assert client.delete("/api/mcp-servers/echo").status_code == 404


# ---------------------------------------------------------------- tool loop + approvals

def tool_call(name="mcp__echo__echo", args='{"text": "hi"}'):
    return {"id": "c1", "type": "function", "function": {"name": name, "arguments": args}}


class Script:
    def __init__(self, *responses):
        self.responses = list(responses)

    async def __call__(self, model, messages, tools=None):
        return self.responses.pop(0) if self.responses else {"content": "done"}


async def _loop(events, policy_decision):
    """Run one 'ask' call; answer the approval as soon as the event arrives."""
    async def on_event(ev):
        events.append(ev)
        if ev["type"] == "tool_approval_required":
            assert mcp_client.resolve_approval(ev["approval_id"], policy_decision)

    return await run_tool_loop(
        Script({"content": "", "tool_calls": [tool_call()]}, {"content": "final"}),
        "m", [{"role": "user", "content": "q"}], [{"t": 1}], on_event=on_event,
    )


def test_ask_approved_runs_tool(echo):
    mcp_client.update_server("echo", {"tool_policies": {"echo": "ask"}})
    events = []
    res = run(_loop(events, True))
    approval = [e for e in events if e["type"] == "tool_approval_required"]
    assert len(approval) == 1 and approval[0]["tool"] == "mcp__echo__echo"
    assert res["tools_executed"][0]["ok"] is True
    assert "echo:hi" in res["messages"][-1]["content"]


def test_ask_denied_does_not_run_tool(echo, monkeypatch):
    mcp_client.update_server("echo", {"tool_policies": {"echo": "ask"}})
    calls = []

    async def spy(name, args, target_workspace=None):
        calls.append(name)
        return "ran"

    monkeypatch.setattr(executor, "execute_tool", spy)
    res = run(_loop([], False))
    assert calls == []
    assert res["tools_executed"][0]["ok"] is False
    assert "not approve" in res["messages"][-1]["content"]


def test_ask_without_a_listener_is_denied(echo, monkeypatch):
    mcp_client.update_server("echo", {"tool_policies": {"echo": "ask"}})
    res = run(run_tool_loop(
        Script({"content": "", "tool_calls": [tool_call()]}, {"content": "final"}),
        "m", [{"role": "user", "content": "q"}], [{"t": 1}],
    ))
    assert res["tools_executed"][0]["ok"] is False


def test_ask_times_out_as_denied(echo, monkeypatch):
    mcp_client.update_server("echo", {"tool_policies": {"echo": "ask"}})
    monkeypatch.setattr(mcp_client, "APPROVAL_TIMEOUT_S", 0.05)
    res = run(run_tool_loop(
        Script({"content": "", "tool_calls": [tool_call()]}, {"content": "final"}),
        "m", [{"role": "user", "content": "q"}], [{"t": 1}], on_event=lambda ev: None,
    ))
    assert res["tools_executed"][0]["ok"] is False
    assert mcp_client._approvals == {}


def test_deny_policy_blocks_before_execute(echo, monkeypatch):
    calls = []

    async def spy(name, args, target_workspace=None):
        calls.append(name)
        return "ran"

    monkeypatch.setattr(executor, "execute_tool", spy)
    res = run(run_tool_loop(
        Script({"content": "", "tool_calls": [tool_call()]}, {"content": "final"}),
        "m", [{"role": "user", "content": "q"}], [{"t": 1}], on_event=lambda ev: None,
    ))
    assert calls == [] and res["tools_executed"][0]["ok"] is False


def test_repeated_ask_call_is_asked_again(echo):
    mcp_client.update_server("echo", {"tool_policies": {"echo": "ask"}})

    async def go():
        events = []

        async def on_event(ev):
            events.append(ev)
            if ev["type"] == "tool_approval_required":
                mcp_client.resolve_approval(ev["approval_id"], True)

        await run_tool_loop(
            Script({"content": "", "tool_calls": [tool_call()]},
                   {"content": "", "tool_calls": [tool_call()]}, {"content": "final"}),
            "m", [{"role": "user", "content": "q"}], [{"t": 1}], on_event=on_event,
        )
        return [e for e in events if e["type"] == "tool_approval_required"]

    assert len(run(go())) == 2  # identical arguments must not reuse the first approval


def test_policy_change_applies_to_repeat_call(echo):
    mcp_client.update_server("echo", {"tool_policies": {"echo": "auto"}})

    async def go():
        async def on_event(ev):
            if ev["type"] == "tool_result":
                mcp_client.update_server("echo", {"tool_policies": {"echo": "deny"}})

        return await run_tool_loop(
            Script({"content": "", "tool_calls": [tool_call()]},
                   {"content": "", "tool_calls": [tool_call()]}, {"content": "final"}),
            "m", [{"role": "user", "content": "q"}], [{"t": 1}], on_event=on_event,
        )

    res = run(go())
    assert [t["ok"] for t in res["tools_executed"]] == [True, False]


def test_id_with_double_underscore_rejected():
    with pytest.raises(mcp_client.McpError):
        mcp_client.add_server({"id": "dev__db", "transport": "http", "url": "http://x"})
    mcp_client.add_server({"id": "dev_db", "transport": "http", "url": "http://x"})


def test_corrupt_store_is_not_overwritten():
    mcp_client.add_server({"id": "keep", "transport": "http", "url": "http://x",
                           "headers": {"Authorization": "Bearer t"}})
    path = mcp_client.servers_file()
    with open(path, "w", encoding="utf-8") as f:
        f.write("{not json")
    with pytest.raises(mcp_client.McpError):
        mcp_client.add_server({"id": "other", "transport": "http", "url": "http://y"})
    with open(path, encoding="utf-8") as f:
        assert f.read() == "{not json"
    assert mcp_client.list_servers() == []  # chat/listing path degrades instead of raising
    os.remove(path)


def test_store_file_is_owner_only():
    mcp_client.add_server({"id": "perm", "transport": "http", "url": "http://x"})
    assert os.stat(mcp_client.servers_file()).st_mode & 0o777 == 0o600


def test_errors_are_scrubbed():
    text = "ConnectError: https://user:pw@host/mcp?token=abc123&x=1 refused"
    scrubbed = mcp_client._scrub(text)
    assert "pw" not in scrubbed and "abc123" not in scrubbed and "x=***" in scrubbed


def test_changed_definition_resets_policy(echo):
    mcp_client.update_server("echo", {"tool_policies": {"echo": "auto"}})
    servers = mcp_client._load_strict()
    servers["echo"]["tools"]["echo"]["fingerprint"] = "stale"  # as if the server had edited it
    mcp_client._save(servers)
    rec = run(mcp_client.refresh_server("echo"))
    tool = {t["name"]: t for t in rec["tools"]}["echo"]
    assert tool["policy"] == "deny" and tool["definition_changed"] is True
    assert mcp_client.get_tool_definitions() == []
    # Re-enabling and refreshing again with an unchanged definition keeps the choice.
    mcp_client.update_server("echo", {"tool_policies": {"echo": "auto"}})
    rec = run(mcp_client.refresh_server("echo"))
    tool = {t["name"]: t for t in rec["tools"]}["echo"]
    assert tool["policy"] == "auto" and tool["definition_changed"] is False


def test_builtin_tools_are_not_gated(monkeypatch):
    async def fake(name, args, target_workspace=None):
        return "ok result"

    monkeypatch.setattr(executor, "execute_tool", fake)
    res = run(run_tool_loop(
        Script({"content": "", "tool_calls": [tool_call("web_search", '{"query": "x"}')]}, {"content": "f"}),
        "m", [{"role": "user", "content": "q"}], [{"t": 1}],
    ))
    assert res["tools_executed"][0]["ok"] is True


def test_approval_resolves_once():
    async def go():
        aid, fut = mcp_client.new_approval()
        assert mcp_client.resolve_approval(aid, True) is True
        assert mcp_client.resolve_approval(aid, False) is False
        return fut.result()

    assert run(go()) is True
    mcp_client._approvals.clear()


def test_approval_endpoint_unknown_id():
    assert client.post("/api/mcp-approvals/unknown", json={"approve": True}).status_code == 404
