from fastapi.testclient import TestClient

from backend import main, storage

client = TestClient(main.app)


def test_second_message_while_streaming_is_rejected_not_dropped(monkeypatch):
    conv = storage.create_conversation("conflict-test")
    running = main.DeliberationContext(conv["id"])
    monkeypatch.setitem(main.ACTIVE_DELIBERATION_CONTEXTS, conv["id"], running)

    resp = client.post(f"/api/conversations/{conv['id']}/message/stream", json={"content": "second"})

    # Used to attach to the running stream and silently lose "second".
    assert resp.status_code == 409
    assert storage.get_conversation(conv["id"])["messages"] == []
