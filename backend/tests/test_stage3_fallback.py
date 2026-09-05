import pytest
from unittest.mock import patch, AsyncMock
from backend.council import (
    get_stage3_fallback_chain,
    stage3_synthesize_final,
    stage3_synthesize_final_streaming,
)


def test_get_stage3_fallback_chain():
    stage1_results = [
        {"model": "local/qwen3.6-27b@karpathy-guidelines", "response": "Simplicity first"},
        {"model": "local/antigravity@differential-review", "response": "Risk assessment"},
        {"model": "local/qwen3.6-27b@testing-handbook", "response": "Test harnesses"},
    ]
    chain = get_stage3_fallback_chain("local/claude-code", stage1_results)

    # Primary should be first
    assert chain[0] == "local/claude-code"
    # Antigravity should be prioritized as peer counterpart
    assert "local/antigravity" in chain[:3]
    # Succeeded Stage 1 models should be present without @skill suffix
    assert "local/qwen3.6-27b" in chain
    assert not any("@" in m for m in chain)
    # Deduplication
    assert len(chain) == len(set(chain))


@pytest.mark.asyncio
async def test_stage3_synthesize_final_failover():
    stage1 = [
        {"model": "local/qwen3.6-27b@karpathy-guidelines", "response": "Keep schema simple."},
        {"model": "local/antigravity@differential-review", "response": "Evaluate rollback risk."},
    ]
    stage2 = [
        {"model": "local/qwen3.6-27b@karpathy-guidelines", "ranking": "1. Response B\n2. Response A"},
    ]

    # First model (claude-code) fails (returns None), second model (antigravity) succeeds
    async def mock_query(model, messages, timeout=None):
        if model == "local/claude-code":
            return None
        if model == "local/antigravity":
            return {
                "content": "## Verdict: Migrate to SQLite WAL\n**Recommendation:** Use WAL mode.\n**Dissenting risk:** None.",
                "usage": {"total_tokens": 150},
                "cost": {"total_cost": 0.001},
            }
        return None

    with patch("backend.council.query_model", side_effect=mock_query):
        result = await stage3_synthesize_final("Migrate to SQLite?", stage1, stage2, model="local/claude-code")

        assert result["model"] == "local/antigravity"
        assert result["is_fallback"] is True
        assert "Verdict: Migrate to SQLite WAL" in result["response"]


@pytest.mark.asyncio
async def test_stage3_synthesize_final_graceful_degradation():
    stage1 = [
        {"model": "local/qwen3.6-27b@karpathy-guidelines", "response": "Detailed recommendation from Karpathy seat."},
    ]
    stage2 = []

    # All models fail
    with patch("backend.council.query_model", return_value=None):
        result = await stage3_synthesize_final("High stakes question", stage1, stage2, model="local/claude-code")

        assert result.get("degraded") is True
        assert "Consensus Adopted (Chairman Failover)" in result["response"]
        assert "Detailed recommendation from Karpathy seat." in result["response"]


@pytest.mark.asyncio
async def test_stage3_synthesize_final_streaming_failover():
    stage1 = [
        {"model": "local/qwen3.6-27b@karpathy-guidelines", "response": "Answer 1"},
    ]
    stage2 = []

    async def mock_streaming(model, messages):
        if model == "local/claude-code":
            yield {"type": "error", "error": "502 Bad Gateway"}
            return
        if model == "local/antigravity":
            yield {"type": "token", "content": "Fallback "}
            yield {"type": "token", "content": "synthesis"}
            yield {"type": "complete", "content": "Fallback synthesis", "usage": {}, "cost": {}}
            return

    with patch("backend.council.query_model_streaming", side_effect=mock_streaming):
        events = []
        async for event in stage3_synthesize_final_streaming("Question", stage1, stage2, model="local/claude-code"):
            events.append(event)

        event_types = [e["type"] for e in events]
        assert "stage3_token" in event_types
        assert "stage3_complete" in event_types
        assert events[-1]["response"] == "Fallback synthesis"
        assert events[-1]["model"] == "local/antigravity"
