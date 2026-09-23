import pytest
from fastapi.testclient import TestClient
from backend.main import app, ACTIVE_DELIBERATION_CONTEXTS, DeliberationContext
from backend import storage

client = TestClient(app)

def test_get_conversation_self_healing(tmp_path, monkeypatch):
    """Test that a conversation stuck in deliberating or streaming heals to idle if no active context exists."""
    conv_id = "test-heal-conv"
    conv_data = {
        "id": conv_id,
        "title": "Test Healing",
        "created_at": "2026-09-13T20:00:00",
        "status": "deliberating",
        "messages": []
    }
    
    # Ensure no active context in memory
    ACTIVE_DELIBERATION_CONTEXTS.pop(conv_id, None)
    
    monkeypatch.setattr(storage, "get_conversation", lambda cid: dict(conv_data) if cid == conv_id else None)
    
    saved_conversations = []
    def mock_save(conversation):
        saved_conversations.append(dict(conversation))
        conv_data.update(conversation)

    monkeypatch.setattr(storage, "save_conversation", mock_save)
    
    response = client.get(f"/api/conversations/{conv_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "idle"
    assert len(saved_conversations) == 1
    assert saved_conversations[0]["status"] == "idle"


def test_reconnect_events_not_found():
    """Test that requesting events for a non-existent active stream returns 404."""
    conv_id = "non-existent-stream-id"
    ACTIVE_DELIBERATION_CONTEXTS.pop(conv_id, None)
    
    response = client.get(f"/api/conversations/{conv_id}/events")
    assert response.status_code == 404
    assert "No active stream" in response.json()["detail"]


@pytest.mark.asyncio
async def test_deliberation_context_replay_and_subscribe():
    """Test that DeliberationContext buffers history and replays to late subscribers."""
    ctx = DeliberationContext(conversation_id="test-ctx-id")
    
    # Broadcast some initial events
    ctx.broadcast('data: {"type": "stage1_start"}\n\n')
    ctx.broadcast('data: {"type": "stage1_token", "text": "hello"}\n\n')
    
    assert len(ctx.history) == 2
    
    # Subscribe after events occurred
    q = ctx.add_subscriber()
    assert q.qsize() == 2
    
    item1 = await q.get()
    assert "stage1_start" in item1
    item2 = await q.get()
    assert "stage1_token" in item2
    
    # New event should also reach subscriber
    ctx.broadcast('data: {"type": "complete"}\n\n')
    assert q.qsize() == 1
    item3 = await q.get()
    assert "complete" in item3
    
    ctx.remove_subscriber(q)
    assert q not in ctx.subscribers
