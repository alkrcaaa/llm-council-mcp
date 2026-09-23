import pytest
from unittest.mock import patch, AsyncMock
from backend import providers


def test_provider_presets_structure():
    presets = providers.PROVIDER_PRESETS
    assert "google" in presets
    assert "groq" in presets
    assert "deepseek" in presets
    assert "ollama" in presets

    google = presets["google"]
    assert google["base_url"].startswith("https://generativelanguage.googleapis.com")
    assert google["default_model"] == "gemini-3.6-flash"
    assert google["provider_type"] == "remote"


def test_add_or_update_provider_with_preset():
    with patch("backend.providers.load_providers", return_value=[]), \
         patch("backend.providers.save_providers", return_value=True):
        entry = providers.add_or_update_provider({
            "preset": "google",
            "api_key": "dummy_key",
            "model_id": "gemini-3.6-flash",
        })
        assert entry["name"] == "Google AI Studio (Gemini)"
        assert entry["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai"
        assert entry["provider_type"] == "remote"
        assert entry["model_id"] == "gemini-3.6-flash"
        assert entry["preset"] == "google"


@pytest.mark.asyncio
async def test_fetch_models_parsing():
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {"id": "models/gemini-2.5-pro"},
            {"id": "models/gemini-3.6-flash"},
            {"id": "models/text-embedding-004"},
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        res = await providers.fetch_models_from_endpoint(
            preset="google",
            api_key="test-key"
        )
        assert res["success"] is True
        assert res["count"] == 3
        # Ensure 'models/' prefix is stripped and chat models are prioritized
        assert res["models"][0] == "gemini-3.6-flash"
        assert res["models"][1] == "gemini-2.5-pro"
        assert "text-embedding-004" in res["models"]


def test_add_or_update_ollama_local_registration():
    with patch("backend.providers.load_providers", return_value=[]), \
         patch("backend.providers.save_providers", return_value=True):
        entry = providers.add_or_update_provider({
            "preset": "ollama",
            "base_url": "http://localhost:11434",
            "model_id": "llama3.3:latest",
        })
        # Verifies ID starts with local/
        assert entry["id"] == "local/llama3.3:latest"
        assert entry["provider_type"] == "local"
        # Verifies localhost was converted to host.docker.internal and /v1 appended
        assert entry["base_url"] == "http://host.docker.internal:11434/v1"
        assert entry["api_key"] == "not-needed"


def test_local_model_pricing_zero_cost():
    from backend.pricing import get_model_pricing
    assert get_model_pricing("local/llama3.3:latest") == {"input": 0.0, "output": 0.0}
    assert get_model_pricing("local/qwen2.5:7b@owasp-security") == {"input": 0.0, "output": 0.0}
