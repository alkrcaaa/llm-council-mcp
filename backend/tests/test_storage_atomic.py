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
