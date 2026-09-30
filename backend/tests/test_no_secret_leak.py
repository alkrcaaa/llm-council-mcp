"""Every GET response must be free of configured secrets and key-shaped strings."""

import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend import providers
from backend.main import app

client = TestClient(app)

SECRETS = {
    "OPENROUTER_API_KEY": "sk-or-v1-leaktest0123456789abcdef",
    "CLAUDE_SHIM_SECRET": "shim-secret-leaktest-claude",
    "ANTIGRAVITY_SHIM_SECRET": "shim-secret-leaktest-agy",
    "QWEN_API_KEY": "qwen-key-leaktest-0123456789",
    "GITHUB_TOKEN": "ghp_leaktest0123456789abcdefghijklmnopqr",
    "JWT_SECRET": "jwt-secret-leaktest-0123456789",
}
CUSTOM_KEY = "custom-provider-key-leaktest-987654"

KEY_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


@pytest.fixture
def seeded(monkeypatch):
    for name, value in SECRETS.items():
        monkeypatch.setenv(name, value)
    saved = providers.add_or_update_provider({
        "id": "leaktest",
        "name": "Leak Test",
        "base_url": "https://api.example.com/v1",
        "api_key": CUSTOM_KEY,
        "model_id": "m1",
    })
    yield saved
    providers.delete_provider(saved["id"])


def _get_urls(provider_id):
    for route in app.routes:
        if isinstance(route, APIRoute) and "GET" in (route.methods or ()):
            path = re.sub(r"\{provider_id[^}]*\}", provider_id, route.path)
            yield re.sub(r"\{[^}]+\}", "x", path)


def test_no_get_response_contains_a_secret(seeded):
    needles = [*SECRETS.values(), CUSTOM_KEY]
    leaks = []
    answered = 0
    for url in _get_urls(seeded["id"]):
        resp = client.get(url)
        answered += resp.status_code == 200
        body = resp.text
        leaks += [f"{url}: configured secret" for n in needles if n in body]
        leaks += [f"{url}: {p.pattern}" for p in KEY_PATTERNS if p.search(body)]
    assert leaks == []
    # A sweep where most routes answer 401 proves nothing.
    assert answered >= 15, f"only {answered} GET routes answered 200"
