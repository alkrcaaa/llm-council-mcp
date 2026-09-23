import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend import auth
from backend.main import PUBLIC_PATHS, app

client = TestClient(app)


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setattr(auth, "JWT_SECRET", "test-secret")


def _protected_routes():
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path not in PUBLIC_PATHS:
            for method in route.methods:
                # Fill path params with a dummy value so the route matches.
                yield method, route.path, re.sub(r"\{[^}]+\}", "x", route.path)


def test_every_non_public_route_rejects_missing_token(auth_on):
    # Guards the old failure mode: auth was added per route and ~55 routes were missed.
    open_routes = []
    for method, path, url in _protected_routes():
        resp = client.request(method, url)
        if resp.status_code != 401:
            open_routes.append(f"{method} {path} -> {resp.status_code}")
    assert open_routes == []


def test_public_routes_need_no_token(auth_on):
    assert client.get("/").status_code == 200
    assert client.get("/api/auth/status").status_code == 200
    bad_login = client.post("/api/auth/login", json={"username": "x", "password": "y"})
    assert bad_login.status_code == 401


def test_valid_token_is_accepted(auth_on):
    token = auth.create_token("admin")
    resp = client.get("/api/councils", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_tampered_token_is_rejected(auth_on):
    token = auth.create_token("admin")[:-2] + "xx"
    resp = client.get("/api/councils", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
