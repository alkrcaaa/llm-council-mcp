import os
import pytest
from unittest.mock import patch
from backend.main import SendMessageRequest
from backend import storage, councils
import importlib.util
from pathlib import Path

_server_path = Path(__file__).parent.parent.parent / "mcp" / "server.py"
_spec = importlib.util.spec_from_file_location("council_mcp_server", _server_path)
_mcp_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mcp_server)

get_caller_model_id = _mcp_server.get_caller_model_id
filter_panelists_for_caller = _mcp_server.filter_panelists_for_caller


def test_get_caller_model_id_claude():
    with patch.dict(os.environ, {"CLAUDE_CODE": "1", "ANTIGRAVITY_AGENT": ""}, clear=True):
        assert get_caller_model_id() == "local/claude-code"

    with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": "/tmp/proj"}, clear=True):
        assert get_caller_model_id() == "local/claude-code"


def test_get_caller_model_id_antigravity():
    with patch.dict(os.environ, {"ANTIGRAVITY_AGENT": "1"}, clear=True):
        assert get_caller_model_id() == "local/antigravity"

    with patch.dict(os.environ, {"AI_AGENT": "antigravity"}, clear=True):
        assert get_caller_model_id() == "local/antigravity"

    with patch.dict(os.environ, {"ANTIGRAVITY_CONVERSATION_ID": "test-uuid"}, clear=True):
        assert get_caller_model_id() == "local/antigravity"


def test_get_caller_model_id_none():
    with patch.dict(os.environ, {}, clear=True):
        with patch("sys.argv", ["mcp-server"]):
            assert get_caller_model_id() is None


def test_filter_panelists_for_antigravity():
    panel = [
        "local/antigravity@red-team-reasoning",
        "local/qwen3.6-27b@first-principles",
        "local/qwen3.6-27b@deep-research",
    ]
    filtered = filter_panelists_for_caller(panel, "local/antigravity")
    assert filtered == [
        "local/qwen3.6-27b@first-principles",
        "local/qwen3.6-27b@deep-research",
    ]
    assert len(filtered) == 2


def test_filter_panelists_for_claude():
    panel = [
        "local/antigravity@red-team-reasoning",
        "local/qwen3.6-27b@first-principles",
        "local/qwen3.6-27b@deep-research",
    ]
    filtered = filter_panelists_for_caller(panel, "local/claude-code")
    # Claude is not on this board, so panel remains intact
    assert filtered == panel


def test_filter_panelists_strips_claude_when_present():
    panel = [
        "local/claude-code@code-review",
        "local/qwen3.6-27b@first-principles",
        "local/qwen3.6-27b@deep-research",
    ]
    filtered = filter_panelists_for_caller(panel, "local/claude-code")
    assert filtered == [
        "local/qwen3.6-27b@first-principles",
        "local/qwen3.6-27b@deep-research",
    ]


def test_send_message_request_accepts_council_models():
    req = SendMessageRequest(
        content="Test question",
        council_models=["local/qwen3.6-27b@first-principles", "local/qwen3.6-27b@deep-research"],
    )
    assert req.council_models == [
        "local/qwen3.6-27b@first-principles",
        "local/qwen3.6-27b@deep-research",
    ]


@pytest.mark.asyncio
async def test_send_message_syncs_overridden_council_models():
    # Setup a mock conversation in storage
    conv_id = "test-caller-filter-conv"
    c_obj = councils.get_council_by_id("cognitive-strategy")
    conv = storage.create_conversation(
        conv_id,
        council_id=c_obj["id"],
        council_name=c_obj["name"],
        council_models=c_obj["council_models"],
        chairman_model=c_obj["chairman_model"],
    )

    assert "local/antigravity@red-team-reasoning" in conv["council_models"]

    # Now simulate a send_message request with filtered council_models
    filtered_models = [
        "local/qwen3.6-27b@first-principles",
        "local/qwen3.6-27b@deep-research",
    ]
    req = SendMessageRequest(
        content="Should we use rust?",
        council_models=filtered_models,
        chairman_model="local/claude-code",
    )

    with patch("backend.main.run_full_council") as mock_run:
        mock_run.return_value = ([], [], {}, {})
        from backend.main import send_message
        await send_message(conv_id, req)

        # Assert run_full_council received the filtered models
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["council_models"] == filtered_models
        assert call_kwargs["chairman_model"] == "local/claude-code"

        # Assert storage was updated to reflect filtered models
        saved_conv = storage.get_conversation(conv_id)
        assert saved_conv["council_models"] == filtered_models


@pytest.mark.asyncio
async def test_ask_council_insufficient_panelists_guard():
    ask_council = _mcp_server.ask_council
    with patch.dict(os.environ, {"ANTIGRAVITY_AGENT": "1"}, clear=True):
        from unittest.mock import AsyncMock, MagicMock
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "mock-conv-id",
            "council_models": [
                "local/antigravity@red-team-reasoning",
                "local/qwen3.6-27b@first-principles",
            ],
        }
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            verdict = await ask_council(
                question="High stakes database choice",
                type1_rationale="Database migration is irreversible and downtime costs $10k/hr.",
                council_id="two-member-board",
            )
            assert "## Verdict: Council Misconfigured for This Caller" in verdict
            assert "Degenerate single-model deliberation prevented" in verdict
            assert "local/antigravity" in verdict
