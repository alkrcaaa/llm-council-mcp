"""Path sandbox for workspace tools and SSRF guard for web_fetch."""

import asyncio

import pytest

from backend import netguard
from backend.tools import builtin
from backend.tools.registry import get_tools_for_model


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "ws"
    (root / "proj" / "data").mkdir(parents=True)
    (root / "proj" / ".git").mkdir()
    (root / "proj" / "app.py").write_text("print('hi')\n")
    (root / "proj" / ".env").write_text("SECRET=1\n")
    (root / "proj" / ".env.local").write_text("SECRET=2\n")
    (root / "proj" / ".git" / "config").write_text("[remote]\n")
    (root / "proj" / "data" / "providers.json").write_text("{}")
    (tmp_path / "outside.txt").write_text("nope")
    monkeypatch.setattr(builtin, "_workspace_roots", lambda: [root.resolve()])
    return root


def read(path, ws=None):
    return asyncio.run(builtin.tool_workspace_read_file(path, target_workspace=ws))


def test_reads_file_inside_workspace(workspace):
    assert "print('hi')" in read("app.py", "proj")


@pytest.mark.parametrize(
    "path",
    [".env", ".env.local", ".git/config", "data/providers.json"],
)
def test_denies_secret_files(workspace, path):
    out = read(path, "proj")
    assert "SECRET" not in out and "[remote]" not in out
    assert "cannot read" in out


def test_blocks_absolute_path_outside(workspace, tmp_path):
    assert "outside the workspace" in read(str(tmp_path / "outside.txt"))
    assert "outside the workspace" in read("/etc/passwd")


def test_blocks_traversal_and_bad_workspace_name(workspace):
    assert "outside the workspace" in read("../../outside.txt", "proj")
    assert "single directory" in read("app.py", "../proj")


def test_blocks_symlink_escape(workspace, tmp_path):
    (workspace / "proj" / "link.txt").symlink_to(tmp_path / "outside.txt")
    assert "outside the workspace" in read("link.txt", "proj")


def test_roundtable_default_has_no_workspace_tools():
    names = {t["function"]["name"] for t in get_tools_for_model("m", is_roundtable=True)}
    assert "workspace_read_file" not in names and "web_fetch" in names
    names = {t["function"]["name"] for t in get_tools_for_model("m", is_roundtable=True, target_workspace="proj")}
    assert "workspace_read_file" in names


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost:8001/api/providers",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://0.0.0.0/",
        "file:///etc/passwd",
        "ftp://example.com/",
        "http://user:pw@example.com/",
    ],
)
def test_check_url_rejects(url):
    with pytest.raises(netguard.BlockedURL):
        netguard.check_url(url)


def test_web_fetch_reports_block_without_raising():
    out = asyncio.run(builtin.tool_web_fetch("http://169.254.169.254/"))
    assert out.startswith("Error: URL blocked")


def test_redirect_to_private_address_is_blocked(monkeypatch):
    """A public host that redirects to loopback must be refused on the second hop."""

    def fake_resolve(host, port):
        if host == "example.com":
            return "93.184.216.34"
        raise netguard.BlockedURL("non-public")

    monkeypatch.setattr(netguard, "resolve_public", fake_resolve)

    import httpx

    def handler(request):
        return httpx.Response(302, headers={"location": "http://internal.test/admin"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(netguard.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw))

    with pytest.raises(netguard.BlockedURL):
        asyncio.run(netguard.safe_get("http://example.com/"))


def test_body_size_is_capped(monkeypatch):
    monkeypatch.setattr(netguard, "resolve_public", lambda host, port: "93.184.216.34")
    import httpx

    transport = httpx.MockTransport(lambda r: httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * 5000))
    real_client = httpx.AsyncClient
    monkeypatch.setattr(netguard.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw))
    _, body = asyncio.run(netguard.safe_get("http://example.com/", max_bytes=1000))
    assert len(body) == 1000


def test_binary_content_type_is_refused(monkeypatch):
    monkeypatch.setattr(netguard, "resolve_public", lambda host, port: "93.184.216.34")
    import httpx

    transport = httpx.MockTransport(lambda r: httpx.Response(200, headers={"content-type": "application/zip"}, content=b"PK"))
    real_client = httpx.AsyncClient
    monkeypatch.setattr(netguard.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw))
    with pytest.raises(netguard.BlockedURL):
        asyncio.run(netguard.safe_get("http://example.com/"))


def test_update_config_preserves_routing_settings(monkeypatch, tmp_path):
    from backend import config_api

    monkeypatch.setattr(config_api, "CONFIG_FILE", str(tmp_path / "council_config.json"))
    monkeypatch.setattr(config_api, "_ensure_config_dir", lambda: None)
    base = config_api.load_config()
    config_api.save_config({**base, "tier1_models": ["a/x"], "escalation_confidence_threshold": 0.42})

    # What PUT /api/config does: merge the two submitted fields onto the stored config.
    saved = config_api.save_config({
        **config_api.load_config(),
        "council_models": base["council_models"],
        "chairman_model": base["chairman_model"],
    })
    assert saved["tier1_models"] == ["a/x"]
    assert saved["escalation_confidence_threshold"] == 0.42
    assert not (tmp_path / "council_config.json.tmp").exists()


def test_prepare_messages_returns_messages_on_error(monkeypatch):
    from backend import openrouter, skills

    def boom(_):
        raise RuntimeError("bad skill")

    monkeypatch.setattr(skills, "get_skill_instructions", boom)
    msgs = [{"role": "user", "content": "hi"}]
    assert openrouter._prepare_messages_for_model("m@some-skill", msgs) == msgs


def test_skill_import_fetch_refuses_private_hosts():
    from backend import skill_import

    assert asyncio.run(skill_import.fetch_url("http://169.254.169.254/latest/meta-data/")) is None
    assert asyncio.run(skill_import.fetch_url("http://127.0.0.1:8001/api/providers")) is None


def test_skill_id_is_folder_name_and_loadable(tmp_path, monkeypatch):
    from backend import skills

    imported = tmp_path / "imported"
    (imported / "real-folder").mkdir(parents=True)
    (imported / "real-folder" / "SKILL.md").write_text("---\nname: other-name\n---\nbody\n")
    monkeypatch.setattr(skills, "SKILLS_DIR", str(tmp_path / "none"))
    monkeypatch.setattr(skills, "IMPORTED_SKILLS_DIR", str(imported))

    ids = [s["id"] for s in skills.get_available_skills()]
    assert ids == ["real-folder"]
    assert skills.get_skill_instructions("real-folder")


def test_injected_skill_text_is_capped(tmp_path, monkeypatch):
    from backend import skills

    imported = tmp_path / "imported"
    (imported / "big").mkdir(parents=True)
    (imported / "big" / "SKILL.md").write_text("---\nname: big\n---\n" + "x" * 50_000)
    monkeypatch.setattr(skills, "SKILLS_DIR", str(tmp_path / "none"))
    monkeypatch.setattr(skills, "IMPORTED_SKILLS_DIR", str(imported))

    out = skills.get_skill_instructions("big")
    assert out and len(out) < skills.MAX_INJECTED_SKILL_CHARS + 1000


def _limits_client(max_body=100, limit=3):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from backend.limits import LimitsMiddleware, RateLimiter

    app = FastAPI()

    @app.post("/api/research/scout")
    async def scout(request: Request):
        return {"n": len(await request.body())}

    @app.post("/api/config/reset")
    async def other(request: Request):
        return {"n": len(await request.body())}

    app.add_middleware(LimitsMiddleware, max_body=max_body, limiter=RateLimiter(limit=limit))
    return TestClient(app)


def test_oversized_body_is_rejected():
    client = _limits_client()
    assert client.post("/api/config/reset", content=b"x" * 50).status_code == 200
    assert client.post("/api/config/reset", content=b"x" * 500).status_code == 413


def test_chunked_oversized_body_is_rejected():
    client = _limits_client()
    chunks = (b"x" * 60 for _ in range(5))
    assert client.post("/api/config/reset", content=chunks).status_code == 413


def test_costly_endpoint_is_rate_limited_but_others_are_not():
    client = _limits_client(limit=3)
    codes = [client.post("/api/research/scout", content=b"{}").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    assert all(client.post("/api/config/reset", content=b"{}").status_code == 200 for _ in range(10))


def test_get_conversation_does_not_idle_a_running_deliberation(monkeypatch):
    """Runs started by the blocking /message endpoint only register in ACTIVE_DELIBERATIONS."""
    from unittest.mock import MagicMock

    from fastapi.testclient import TestClient

    from backend import main, storage

    client = TestClient(main.app)
    cid = "selfheal-test"
    storage.create_conversation(cid)
    storage.set_conversation_status(cid, "deliberating")

    running = MagicMock()
    running.done.return_value = False
    monkeypatch.setitem(main.ACTIVE_DELIBERATIONS, cid, running)
    assert client.get(f"/api/conversations/{cid}").json()["status"] == "deliberating"
    assert cid in client.get("/api/conversations/active").json()["active_conversations"]

    running.done.return_value = True
    assert client.get(f"/api/conversations/{cid}").json()["status"] == "idle"
    assert storage.get_conversation(cid)["status"] == "idle"
    storage.delete_conversation(cid)
