"""Image attachments reach only vision-capable models, and the internal field never leaves the process."""

import asyncio
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import attachments, capabilities, openrouter, roundtable
from backend.main import app

client = TestClient(app)


@pytest.fixture
def image_ref():
    cid = client.post("/api/conversations", json={}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 0, 0)).save(buf, "PNG")
    meta = client.post(
        f"/api/conversations/{cid}/attachments", files={"file": ("p.png", buf.getvalue())}
    ).json()
    yield cid, meta["id"]
    client.delete(f"/api/conversations/{cid}")


@pytest.mark.parametrize(
    "model,expected",
    [
        ("openai/gpt-4o", True),
        ("anthropic/claude-sonnet-4.5", True),
        ("google/gemini-2.5-pro", True),
        ("qwen/qwen2.5-vl-72b-instruct", True),
        ("meta-llama/llama-3.2-11b-vision-instruct", True),
        ("openai/gpt-4o@owasp-security", True),  # skill suffix is not part of the model
        ("openai/gpt-3.5-turbo", False),
        ("anthropic/claude-2.1", False),
        ("deepseek/deepseek-chat", False),
        ("local/qwen3.6-27b", False),  # unknown means text-only
    ],
)
def test_vision_heuristics(model, expected):
    assert capabilities.supports_vision(model) is expected


def test_env_list_can_enable_a_local_model(monkeypatch):
    monkeypatch.setenv("VISION_MODELS", "local/qwen3.6-27b, other")
    assert capabilities.supports_vision("local/qwen3.6-27b") is True


def test_explicit_flag_beats_name_patterns(monkeypatch):
    from backend import config

    monkeypatch.setitem(config.LOCAL_MODELS, "local/gemini-proxy", {"base_url": "x", "model_id": "m", "vision": False})
    assert capabilities.supports_vision("local/gemini-proxy") is False


def test_custom_endpoint_is_judged_by_its_upstream_model_id(monkeypatch):
    from backend import providers

    records = {
        "custom/gemini-3-6-flash": {"id": "custom/gemini-3-6-flash", "model_id": "gemini-3.6-flash"},
        "custom/groq": {"id": "custom/groq", "model_id": "llama-3.3-70b-versatile"},
    }
    monkeypatch.setattr(providers, "get_provider_by_id", lambda pid: records.get(pid))
    assert capabilities.supports_vision("custom/gemini-3-6-flash") is True
    assert capabilities.supports_vision("custom/groq") is False


def _user(content, refs):
    return {"role": "user", "content": content, "_images": refs}


def test_vision_model_gets_image_parts_and_no_internal_field(image_ref):
    cid, aid = image_ref
    original = [_user("what is this?", [{"c": cid, "id": aid}])]
    out = attachments.inline_images("openai/gpt-4o", original)
    content = out[0]["content"]
    assert content[0] == {"type": "text", "text": "what is this?"}
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "_images" not in out[0]
    assert "_images" in original[0] and original[0]["content"] == "what is this?"  # caller's copy untouched


def test_text_only_model_gets_a_note_and_no_bytes(image_ref):
    cid, aid = image_ref
    out = attachments.inline_images("deepseek/deepseek-chat", [_user("what is this?", [{"c": cid, "id": aid}])])
    assert isinstance(out[0]["content"], str) and "cannot view images" in out[0]["content"]
    assert "base64" not in out[0]["content"] and "_images" not in out[0]


def test_ref_to_another_conversations_file_does_not_resolve(image_ref):
    _, aid = image_ref
    out = attachments.inline_images("openai/gpt-4o", [_user("x", [{"c": "someone-else", "id": aid}])])
    assert isinstance(out[0]["content"], str)  # nothing attached, nothing leaked


def test_messages_without_images_pass_through_untouched():
    msgs = [{"role": "user", "content": "hi"}]
    assert attachments.inline_images("openai/gpt-4o", msgs) is msgs


def test_provider_payload_never_contains_the_internal_field(image_ref, monkeypatch):
    cid, aid = image_ref
    sent = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}], "usage": {}}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            sent["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(openrouter.httpx, "AsyncClient", FakeClient)
    for model in ("openai/gpt-4o", "deepseek/deepseek-chat"):
        asyncio.run(openrouter.query_model(model, [_user("look", [{"c": cid, "id": aid}])]))
        assert "_images" not in str(sent["payload"])


def test_roundtable_prompt_carries_images_on_the_current_turn_even_after_merging():
    refs = [{"c": "c1", "id": "a" * 32}]
    msgs = roundtable.format_roundtable_prompt(
        current_model="m1",
        all_models=["m1", "m2"],
        history_messages=[{"role": "user", "content": "earlier", "sender_name": "User"}],
        user_content="look at this",
        images=refs,
    )
    # History's last user turn and the current one merge into a single user message.
    carriers = [m for m in msgs if m.get("_images")]
    assert len(carriers) == 1 and carriers[0]["_images"] == refs
    assert "look at this" in carriers[0]["content"]


def test_image_refs_only_include_images(image_ref):
    cid, aid = image_ref
    txt = client.post(f"/api/conversations/{cid}/attachments", files={"file": ("a.txt", b"hi")}).json()["id"]
    assert attachments.image_refs(cid, [aid, txt, "0" * 32]) == [{"c": cid, "id": aid}]
