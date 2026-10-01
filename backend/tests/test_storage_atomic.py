import json
import os

from backend import storage


def test_save_conversation_replaces_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", str(tmp_path))
    conv = {"id": "c1", "title": "t", "messages": []}
    storage.save_conversation(conv)

    real_dump = json.dump

    def crash_midway(obj, f, **kw):
        f.write('{"id": "c1", "tit')  # partial write, then the process dies
        raise OSError("disk full")

    monkeypatch.setattr(storage.json, "dump", crash_midway)
    conv["title"] = "new"
    try:
        storage.save_conversation(conv)
    except OSError:
        pass
    monkeypatch.setattr(storage.json, "dump", real_dump)

    # The previous version must survive intact instead of turning into "not found".
    assert storage.get_conversation("c1")["title"] == "t"


def test_save_conversation_leaves_no_temp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", str(tmp_path))
    storage.save_conversation({"id": "c2", "messages": []})
    assert os.listdir(tmp_path) == ["c2.json"]


def test_assistant_message_keeps_metadata_for_reload(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", str(tmp_path))
    storage.save_conversation({"id": "c3", "messages": []})
    meta = {
        "label_to_model": {"Response A": "m/one"},
        "aggregate_rankings": [{"model": "m/one", "average_rank": 1.0}],
        "costs": {"total": {"total_cost": 0.01}},
    }
    storage.add_assistant_message("c3", [{"model": "m/one"}], [], {"response": "x"}, meta)
    storage.add_assistant_message("c3", [], [], {"response": "y"})

    first, second = storage.get_conversation("c3")["messages"]
    assert first["metadata"] == meta
    assert "metadata" not in second  # callers without metadata keep the old shape


def test_user_message_dedup_keeps_same_text_with_new_attachment(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", str(tmp_path))
    storage.save_conversation({"id": "c4", "messages": []})
    a = [{"id": "a1", "kind": "image"}]
    b = [{"id": "b2", "kind": "image"}]
    storage.add_user_message("c4", "look", a)
    storage.add_user_message("c4", "look", a)  # true duplicate
    storage.add_user_message("c4", "look", b)  # same text, different file

    msgs = storage.get_conversation("c4")["messages"]
    assert [m["attachments"] for m in msgs] == [a, b]
