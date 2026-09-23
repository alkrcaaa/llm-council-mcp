from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_get_agent_profiles():
    response = client.get("/api/agent-profiles")
    assert response.status_code == 200
    data = response.json()
    assert "local/antigravity" in data
    assert data["local/antigravity"]["display_name"] == "Antigravity"
    assert "color" in data["local/antigravity"]


def test_update_agent_profile():
    model_id = "local/antigravity"
    payload = {
        "display_name": "Antigravity Master",
        "color": "#123456",
        "avatar_url": "https://example.com/avatar.png",
    }
    response = client.put(f"/api/agent-profiles/{model_id}", json=payload)
    assert response.status_code == 200
    updated = response.json()
    assert updated["display_name"] == "Antigravity Master"
    assert updated["color"] == "#123456"
    assert updated["avatar_url"] == "https://example.com/avatar.png"

    # Verify get endpoint returns the updated profile
    get_res = client.get("/api/agent-profiles")
    assert get_res.status_code == 200
    all_profiles = get_res.json()
    assert all_profiles[model_id]["display_name"] == "Antigravity Master"

    # Reset back to default
    reset_payload = {
        "display_name": "Antigravity",
        "color": "#6366f1",
        "avatar_url": "",
    }
    client.put(f"/api/agent-profiles/{model_id}", json=reset_payload)
