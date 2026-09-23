"""Built-in councils refresh from code, except where the user edited them."""

import json
import pytest

from backend import councils as councils_module


@pytest.fixture
def councils_file(tmp_path, monkeypatch):
    path = tmp_path / "councils.json"
    monkeypatch.setattr(councils_module, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(councils_module, "COUNCILS_FILE", str(path))
    councils_module.load_councils_data()
    return path


def test_edited_builtin_council_survives_a_reload(councils_file):
    councils_module.update_council(
        "cognitive-strategy",
        {"council_models": ["local/antigravity", "local/qwen3.6-27b"], "chairman_model": "local/claude-code"},
    )

    reloaded = councils_module.get_council_by_id("cognitive-strategy")

    assert reloaded["council_models"] == ["local/antigravity", "local/qwen3.6-27b"]
    assert reloaded["chairman_model"] == "local/claude-code"
    assert reloaded["is_builtin"] is True


def test_untouched_builtin_still_refreshes_from_code(councils_file):
    data = json.loads(councils_file.read_text())
    for council in data["councils"]:
        if council["id"] == "code-craft":
            council["council_models"] = ["stale/model-a", "stale/model-b"]
    councils_file.write_text(json.dumps(data))

    reloaded = councils_module.get_council_by_id("code-craft")

    builtin = next(c for c in councils_module.BUILTIN_COUNCILS if c["id"] == "code-craft")
    assert reloaded["council_models"] == builtin["council_models"]


def test_custom_councils_are_untouched_by_the_refresh(councils_file):
    created = councils_module.create_custom_council(
        "My Board", ["local/a", "local/b"], "local/c"
    )

    reloaded = councils_module.get_council_by_id(created["id"])

    assert reloaded["council_models"] == ["local/a", "local/b"]


def test_edited_builtin_chat_roster_survives_a_reload(councils_file):
    councils_module.update_chat_roster(
        "roundtable-core", {"models": ["local/antigravity", "local/claude-code"]}
    )

    reloaded = councils_module.get_chat_roster_by_id("roundtable-core")

    assert reloaded["models"] == ["local/antigravity", "local/claude-code"]
    assert reloaded["is_builtin"] is True


def test_untouched_builtin_roster_still_refreshes_from_code(councils_file):
    data = json.loads(councils_file.read_text())
    for roster in data["chat_rosters"]:
        if roster["id"] == "fast-trio":
            roster["models"] = ["stale/model"]
    councils_file.write_text(json.dumps(data))

    reloaded = councils_module.get_chat_roster_by_id("fast-trio")

    builtin = next(r for r in councils_module.BUILTIN_CHAT_ROSTERS if r["id"] == "fast-trio")
    assert reloaded["models"] == builtin["models"]
