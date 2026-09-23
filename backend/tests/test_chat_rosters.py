from fastapi.testclient import TestClient
from backend.main import app
from backend.councils import (
    get_all_chat_rosters,
    get_active_chat_roster,
    get_active_chat_roster_id,
    set_active_chat_roster,
    get_chat_roster_by_id,
    create_custom_chat_roster,
    update_chat_roster,
    delete_chat_roster,
)


def test_builtin_chat_rosters_exist():
    rosters = get_all_chat_rosters()
    assert len(rosters) >= 3
    ids = [r["id"] for r in rosters]
    assert "fast-trio" in ids
    assert "code-collaborators" in ids
    assert "creative-brainstorm" in ids


def test_active_chat_roster():
    active = get_active_chat_roster()
    assert active is not None
    assert "id" in active
    assert "models" in active
    assert len(active["models"]) >= 1


def test_custom_chat_roster_lifecycle():
    # 1. Create
    created = create_custom_chat_roster(
        name="Test Brainstorm Duo",
        icon="⚡",
        description="Fast test roster",
        models=["liquid/lfm-2.5-2.6b:free@karpathy-guidelines", "local/qwen3.6-27b@deep-research"],
    )
    rid = created["id"]
    assert rid.startswith("roster-")
    assert created["name"] == "Test Brainstorm Duo"
    assert created["is_builtin"] is False

    # 2. Retrieve
    retrieved = get_chat_roster_by_id(rid)
    assert retrieved is not None
    assert retrieved["name"] == "Test Brainstorm Duo"

    # 3. Update
    updated = update_chat_roster(rid, {"name": "Updated Brainstorm Duo"})
    assert updated["name"] == "Updated Brainstorm Duo"

    # 4. Set Active
    set_active_chat_roster(rid)
    assert get_active_chat_roster_id() == rid

    # 5. Delete
    deleted = delete_chat_roster(rid)
    assert deleted is True
    assert get_chat_roster_by_id(rid) is None


def test_chat_rosters_api():
    client = TestClient(app)

    # List rosters
    resp = client.get("/api/chat-rosters")
    assert resp.status_code == 200
    data = resp.json()
    assert "rosters" in data
    assert "active_roster_id" in data
    assert len(data["rosters"]) >= 3

    # Get active roster
    active_resp = client.get("/api/chat-rosters/active")
    assert active_resp.status_code == 200
    active_data = active_resp.json()
    assert "models" in active_data

    # Activate roster
    act_resp = client.post("/api/chat-rosters/fast-trio/activate")
    assert act_resp.status_code == 200
    assert act_resp.json()["id"] == "fast-trio"


def test_chat_settings_and_prompt_injection():
    client = TestClient(app)

    # 1. Get settings
    resp = client.get("/api/chat-settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert "system_prompt" in data

    # 2. Update settings
    custom_text = "### Custom Injected Rules\n- Be concise\n- No emoji"
    update_resp = client.post(
        "/api/chat-settings",
        json={"models": ["local/antigravity", "local/qwen3.6-27b"], "system_prompt": custom_text},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["system_prompt"] == custom_text
    assert len(updated["models"]) == 2

    # 3. Test prompt formatting includes custom context
    from backend.roundtable import format_roundtable_prompt
    messages = format_roundtable_prompt(
        current_model="local/antigravity",
        all_models=["local/antigravity", "local/qwen3.6-27b"],
        history_messages=[],
        user_content="Hello world",
        user_name="Ali",
        custom_context=custom_text,
    )
    sys_msg = next((m for m in messages if m["role"] == "system"), None)
    assert sys_msg is not None
    assert "Custom Injected Rules" in sys_msg["content"]
    assert "No emoji" in sys_msg["content"]

