"""The shims take OpenAI messages whose content may be a list of typed parts."""

import importlib.util
from pathlib import Path

import pytest

SHIM_DIR = Path(__file__).resolve().parents[2] / "infra" / "local-models"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SHIM_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["claude_code_shim", "antigravity_shim"])
def shim(request):
    return _load(request.param)


def test_list_content_is_flattened_to_text(shim):
    messages = [
        {"role": "system", "content": [{"type": "text", "text": "be brief"}]},
        {"role": "user", "content": [
            {"type": "text", "text": "what is this?"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
        ]},
    ]
    prompt = shim.messages_to_prompt(messages)
    assert "be brief" in prompt and "what is this?" in prompt
    assert "[image omitted]" in prompt and "AAAA" not in prompt


def test_none_and_string_content_still_work(shim):
    prompt = shim.messages_to_prompt([
        {"role": "assistant", "content": None},
        {"role": "user", "content": "hello"},
    ])
    assert "hello" in prompt
