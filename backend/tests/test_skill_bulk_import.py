"""Tests for discovering and bulk importing the skills inside a repository."""

import asyncio
import pytest

from backend import skill_import, skill_jobs
from backend import skills as skills_module


def run(coro):
    return asyncio.run(coro)


TREE = {
    "tree": [
        {"path": "README.md", "type": "blob"},
        {"path": "skills/rdkit/SKILL.md", "type": "blob"},
        {"path": "skills/rdkit/scripts/run.py", "type": "blob"},
        {"path": "skills/scanpy/SKILL.md", "type": "blob"},
        {"path": "docs/guide.md", "type": "blob"},
    ]
}


@pytest.fixture
def skill_dirs(tmp_path, monkeypatch):
    curated = tmp_path / "skills"
    imported = tmp_path / "skills-imported"
    curated.mkdir()
    imported.mkdir()
    monkeypatch.setattr(skills_module, "SKILLS_DIR", str(curated))
    monkeypatch.setattr(skills_module, "IMPORTED_SKILLS_DIR", str(imported))
    return curated, imported


# --- discovery ------------------------------------------------------------

def test_lists_every_skill_in_the_repository(monkeypatch):
    async def fake_fetch_json(url):
        assert "K-Dense-AI/scientific-agent-skills" in url
        return TREE

    monkeypatch.setattr(skill_import, "fetch_json", fake_fetch_json)

    result = run(skill_import.list_repo_skills("https://github.com/K-Dense-AI/scientific-agent-skills"))

    assert result["repo"] == "K-Dense-AI/scientific-agent-skills"
    assert [s["id"] for s in result["skills"]] == ["rdkit", "scanpy"]
    assert result["skills"][0]["raw_url"] == (
        "https://raw.githubusercontent.com/K-Dense-AI/scientific-agent-skills/main/skills/rdkit/SKILL.md"
    )
    assert result["skills"][0]["origin"] == (
        "https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/rdkit"
    )


def test_tree_url_only_lists_skills_under_that_path(monkeypatch):
    monkeypatch.setattr(skill_import, "fetch_json", lambda url: _json(TREE))

    result = run(
        skill_import.list_repo_skills("https://github.com/owner/repo/tree/main/skills/scanpy")
    )

    assert [s["id"] for s in result["skills"]] == ["scanpy"]


async def _json(payload):
    return payload


def test_root_skill_md_is_listed_under_the_repo_name(monkeypatch):
    monkeypatch.setattr(
        skill_import, "fetch_json",
        lambda url: _json({"tree": [{"path": "SKILL.md", "type": "blob"}]}),
    )

    result = run(skill_import.list_repo_skills("https://github.com/owner/My-Skill"))

    assert [s["id"] for s in result["skills"]] == ["my-skill"]


def test_discovery_requires_a_github_repository():
    with pytest.raises(ValueError):
        run(skill_import.list_repo_skills("https://example.com/some/page"))


def test_unreachable_tree_api_raises(monkeypatch):
    monkeypatch.setattr(skill_import, "fetch_json", lambda url: _json(None))

    with pytest.raises(ValueError):
        run(skill_import.list_repo_skills("https://github.com/owner/repo"))


def test_finds_the_install_command_in_a_readme():
    readme = (
        "# Skills\n\n### Option 1: npx\n\n```bash\nnpx skills add K-Dense-AI/scientific-agent-skills\n```\n\n"
        "### Option 2\n\n```bash\ngh skill install K-Dense-AI/scientific-agent-skills\n```\n"
    )

    assert skill_import.find_install_command(readme) == "npx skills add K-Dense-AI/scientific-agent-skills"
    assert skill_import.find_install_command("# nothing here\n") is None


# --- bulk import job ------------------------------------------------------

SKILL_MD = '---\nname: {id}\ndescription: "Imported {id}"\n---\n\n<!-- gate:begin -->\n- rule\n<!-- gate:end -->\n'


def _entries(*ids):
    return [
        {"id": i, "raw_url": f"https://raw.githubusercontent.com/o/r/main/skills/{i}/SKILL.md",
         "origin": f"https://github.com/o/r/tree/main/skills/{i}"}
        for i in ids
    ]


def test_bulk_import_writes_every_selected_skill(skill_dirs, monkeypatch):
    async def fake_fetch_url(url):
        return SKILL_MD.format(id=url.split("/")[-2])

    monkeypatch.setattr(skill_jobs, "fetch_url", fake_fetch_url)

    job = skill_jobs.create_job(_entries("rdkit", "scanpy"))
    run(skill_jobs.run_job(job["id"]))

    finished = skill_jobs.get_job(job["id"])
    assert finished["status"] == "done"
    assert finished["completed"] == 2
    assert sorted(finished["imported"]) == ["rdkit", "scanpy"]
    assert {s["id"] for s in skills_module.get_available_skills()} == {"rdkit", "scanpy"}


def test_bulk_import_skips_existing_and_records_failures(skill_dirs, monkeypatch):
    skills_module.save_imported_skill("rdkit", SKILL_MD.format(id="rdkit"))

    async def flaky_fetch_url(url):
        return None if "scanpy" in url else SKILL_MD.format(id=url.split("/")[-2])

    monkeypatch.setattr(skill_jobs, "fetch_url", flaky_fetch_url)

    job = skill_jobs.create_job(_entries("rdkit", "scanpy", "aeon"))
    run(skill_jobs.run_job(job["id"]))

    finished = skill_jobs.get_job(job["id"])
    assert finished["status"] == "done"
    assert finished["imported"] == ["aeon"]
    assert finished["skipped"] == ["rdkit"]
    assert [e["id"] for e in finished["errors"]] == ["scanpy"]
    assert finished["completed"] == 3


def test_bulk_import_reports_progress_while_running(skill_dirs, monkeypatch):
    async def fake_fetch_url(url):
        return SKILL_MD.format(id=url.split("/")[-2])

    monkeypatch.setattr(skill_jobs, "fetch_url", fake_fetch_url)

    job = skill_jobs.create_job(_entries("rdkit", "scanpy"))
    assert job["status"] == "pending"
    assert job["total"] == 2
    assert job["completed"] == 0

    run(skill_jobs.run_job(job["id"]))
    assert skill_jobs.get_job(job["id"])["finished_at"] is not None


def test_unknown_job_is_none():
    assert skill_jobs.get_job("nope") is None
