"""Tests for per-provider display labels (e.g. "Sonnet 4.5 - high effort")."""

import json
import pytest

from backend import providers as providers_module


@pytest.fixture
def labels_file(tmp_path, monkeypatch):
    path = tmp_path / "provider_labels.json"
    monkeypatch.setattr(providers_module, "PROVIDER_LABELS_FILE", str(path))
    return path


def test_label_round_trips_through_the_store(labels_file):
    providers_module.set_provider_label("local/claude-code", "Sonnet 4.5 · high effort")

    assert providers_module.get_provider_label("local/claude-code") == "Sonnet 4.5 · high effort"
    assert json.loads(labels_file.read_text())["local/claude-code"] == "Sonnet 4.5 · high effort"


def test_empty_label_clears_the_entry(labels_file):
    providers_module.set_provider_label("local/claude-code", "Sonnet")
    providers_module.set_provider_label("local/claude-code", "  ")

    assert providers_module.get_provider_label("local/claude-code") == ""
    assert json.loads(labels_file.read_text()) == {}


def test_overlong_label_is_rejected(labels_file):
    with pytest.raises(ValueError):
        providers_module.set_provider_label("local/claude-code", "x" * 200)


def test_unknown_provider_has_no_label(labels_file):
    assert providers_module.get_provider_label("local/nothing") == ""


def test_system_providers_carry_their_label(labels_file):
    providers_module.set_provider_label("local/claude-code", "Sonnet 4.5 · high effort")

    system = {p["id"]: p for p in providers_module.get_system_providers()}

    assert system["local/claude-code"]["label"] == "Sonnet 4.5 · high effort"
    assert system["local/qwen3.6-27b"]["label"] == ""


def test_custom_providers_carry_their_label(labels_file, tmp_path, monkeypatch):
    store = tmp_path / "custom_providers.json"
    store.write_text(json.dumps([
        {"id": "custom/groq", "name": "Groq", "provider_type": "remote",
         "base_url": "https://api.groq.com/openai/v1", "model_id": "llama-3.3-70b"}
    ]))
    monkeypatch.setattr(providers_module, "PROVIDERS_FILE", str(store))
    providers_module.set_provider_label("custom/groq", "Llama 3.3 70B")

    loaded = {p["id"]: p for p in providers_module.load_providers()}

    assert loaded["custom/groq"]["label"] == "Llama 3.3 70B"


def test_label_endpoint_updates_and_is_served_with_providers(labels_file, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app, require_auth

    app.dependency_overrides[require_auth] = lambda: None
    client = TestClient(app)
    try:
        response = client.put(
            "/api/providers/local/claude-code/label", json={"label": "Sonnet 4.5 · high effort"}
        )
        assert response.status_code == 200

        listed = {p["id"]: p for p in client.get("/api/providers").json()["providers"]}
        assert listed["local/claude-code"]["label"] == "Sonnet 4.5 · high effort"

        too_long = client.put("/api/providers/local/claude-code/label", json={"label": "x" * 200})
        assert too_long.status_code == 422
    finally:
        app.dependency_overrides.clear()
