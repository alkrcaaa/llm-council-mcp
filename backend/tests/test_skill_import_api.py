"""Tests for the skill import endpoints."""

import os
import pytest
from fastapi.testclient import TestClient

from backend import skills as skills_module
from backend.main import app, require_auth

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_auth():
    app.dependency_overrides[require_auth] = lambda: None
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def skill_dirs(tmp_path, monkeypatch):
    curated = tmp_path / "skills"
    imported = tmp_path / "skills-imported"
    curated.mkdir()
    imported.mkdir()
    monkeypatch.setattr(skills_module, "SKILLS_DIR", str(curated))
    monkeypatch.setattr(skills_module, "IMPORTED_SKILLS_DIR", str(imported))
    return curated, imported


SKILL_MD = '---\nname: pasted-skill\ndescription: "Pasted"\n---\n\n<!-- gate:begin -->\n- rule one\n<!-- gate:end -->\n'


def test_preview_returns_skill_without_writing_it(skill_dirs):
    _, imported = skill_dirs

    response = client.post("/api/skills/import/preview", json={"markdown": SKILL_MD})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "pasted-skill"
    assert body["method"] == "passthrough"
    assert "rule one" in body["checklist"]
    assert os.listdir(str(imported)) == []


def test_preview_rejects_empty_request():
    response = client.post("/api/skills/import/preview", json={})
    assert response.status_code == 422


def test_import_writes_skill_and_lists_it(skill_dirs):
    response = client.post(
        "/api/skills/import",
        json={"skill_id": "pasted-skill", "skill_md": SKILL_MD, "origin": "https://github.com/o/r"},
    )

    assert response.status_code == 200
    assert response.json()["skill"]["source"] == "imported"

    listed = {s["id"]: s for s in client.get("/api/skills").json()["skills"]}
    assert listed["pasted-skill"]["source"] == "imported"
    assert listed["pasted-skill"]["origin"] == "https://github.com/o/r"


def test_import_rejects_duplicate_id(skill_dirs):
    payload = {"skill_id": "pasted-skill", "skill_md": SKILL_MD}
    assert client.post("/api/skills/import", json=payload).status_code == 200

    conflict = client.post("/api/skills/import", json=payload)
    assert conflict.status_code == 409

    assert client.post("/api/skills/import", json={**payload, "overwrite": True}).status_code == 200


def test_delete_removes_imported_skill(skill_dirs):
    client.post("/api/skills/import", json={"skill_id": "pasted-skill", "skill_md": SKILL_MD})

    assert client.delete("/api/skills/pasted-skill").status_code == 200
    assert client.get("/api/skills").json()["skills"] == []


def test_delete_missing_skill_returns_404(skill_dirs):
    assert client.delete("/api/skills/nope").status_code == 404


# --- repository discovery and bulk import --------------------------------

REPO_TREE = {
    "tree": [
        {"path": "README.md", "type": "blob"},
        {"path": "skills/rdkit/SKILL.md", "type": "blob"},
        {"path": "skills/scanpy/SKILL.md", "type": "blob"},
    ]
}

COLLECTION_README = "# Skills\n\n```bash\nnpx skills add owner/collection\n```\n"


def _fake_repo(monkeypatch):
    from backend import skill_import, skill_jobs

    async def fake_fetch_json(url):
        return REPO_TREE

    async def fake_fetch_url(url):
        if url.endswith("README.md"):
            return COLLECTION_README
        if url.endswith("SKILL.md"):
            skill = url.split("/")[-2]
            return f'---\nname: {skill}\ndescription: "Imported {skill}"\n---\n\nbody\n'
        return None

    monkeypatch.setattr(skill_import, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(skill_import, "fetch_url", fake_fetch_url)
    monkeypatch.setattr(skill_jobs, "fetch_url", fake_fetch_url)


def test_discover_lists_repository_skills_and_install_command(skill_dirs, monkeypatch):
    _fake_repo(monkeypatch)

    response = client.post("/api/skills/import/discover", json={"url": "https://github.com/owner/collection"})

    assert response.status_code == 200
    body = response.json()
    assert [s["id"] for s in body["skills"]] == ["rdkit", "scanpy"]
    assert body["install_command"] == "npx skills add owner/collection"


def test_discover_rejects_a_non_repository_url():
    assert client.post("/api/skills/import/discover", json={"url": "https://example.com/x"}).status_code == 422


def test_bulk_import_runs_in_the_background_and_reports_its_result(skill_dirs, monkeypatch):
    _fake_repo(monkeypatch)
    entries = client.post(
        "/api/skills/import/discover", json={"url": "https://github.com/owner/collection"}
    ).json()["skills"]

    started = client.post("/api/skills/import/bulk", json={"entries": entries})
    assert started.status_code == 200
    job_id = started.json()["job"]["id"]

    job = client.get(f"/api/skills/import/jobs/{job_id}").json()
    assert job["status"] == "done"
    assert sorted(job["imported"]) == ["rdkit", "scanpy"]
    assert {s["id"] for s in client.get("/api/skills").json()["skills"]} == {"rdkit", "scanpy"}


def test_bulk_import_rejects_entries_from_other_hosts(skill_dirs, monkeypatch):
    _fake_repo(monkeypatch)

    response = client.post(
        "/api/skills/import/bulk",
        json={"entries": [{"id": "evil", "raw_url": "http://127.0.0.1:8001/api/config"}]},
    )

    assert response.status_code == 422


def test_unknown_job_returns_404():
    assert client.get("/api/skills/import/jobs/nope").status_code == 404
