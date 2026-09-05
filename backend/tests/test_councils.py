import pytest
from backend.councils import (
    get_all_councils,
    get_active_council,
    get_active_council_id,
    set_active_council,
    get_council_by_id,
    create_custom_council,
    update_council,
    delete_council,
)


def test_builtin_councils_exist():
    councils = get_all_councils()
    assert len(councils) >= 5
    ids = [c["id"] for c in councils]
    assert "cognitive-strategy" in ids
    assert "code-craft" in ids
    assert "deep-tech" in ids
    assert "sec-ops" in ids
    assert "frontend-craft" in ids
    assert "tech-scout" in ids


def test_active_council():
    active = get_active_council()
    assert active is not None
    assert "id" in active
    assert "council_models" in active
    assert "chairman_model" in active


def test_custom_council_lifecycle():
    # 1. Create
    created = create_custom_council(
        name="Test Architecture Review",
        icon="🏛️",
        description="Testing council profile",
        council_models=["local/qwen3.6-27b@karpathy-guidelines", "local/antigravity"],
        chairman_model="local/antigravity",
    )
    cid = created["id"]
    assert cid.startswith("council-")
    assert created["name"] == "Test Architecture Review"
    assert created["is_builtin"] is False

    # 2. Retrieve
    retrieved = get_council_by_id(cid)
    assert retrieved is not None
    assert retrieved["name"] == "Test Architecture Review"

    # 3. Update
    updated = update_council(cid, {"name": "Updated Architecture Board"})
    assert updated["name"] == "Updated Architecture Board"

    # 4. Set Active
    set_active_council(cid)
    assert get_active_council_id() == cid

    # 5. Delete
    deleted = delete_council(cid)
    assert deleted is True
    assert get_council_by_id(cid) is None

    # Cannot delete built-in
    assert delete_council("cognitive-strategy") is False
