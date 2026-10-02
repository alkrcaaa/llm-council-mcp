import asyncio
from unittest.mock import patch

from backend import debate


def test_collect_rebuttals_reports_critic_and_failures():
    positions = [{"model": "a", "position": "pa"}, {"model": "b", "position": "pb"}]
    critiques = [
        {"critic": "b", "target": "a", "critique": "ca"},
        {"critic": "a", "target": "b", "critique": "cb"},
    ]
    labels = {"a": "Model A", "b": "Model B"}

    async def fake_query(model, prompt):
        if model == "b":
            raise RuntimeError("boom")
        return {"content": "defence", "cost": {}}

    with patch("backend.openrouter.query_model", fake_query):
        rebuttals, _, failures = asyncio.run(
            debate.collect_rebuttals("q", positions, critiques, labels)
        )

    assert [r["model"] for r in rebuttals] == ["a"]
    assert rebuttals[0]["critic"] == "b"
    assert rebuttals[0]["critic_label"] == "Model B"
    assert failures == [{"model": "b", "error": "boom"}]
