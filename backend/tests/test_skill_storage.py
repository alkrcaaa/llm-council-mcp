"""Tests for the two-directory skill storage (curated library + imported skills)."""

import os
import pytest

from backend import skills as skills_module


def _write_skill(root, skill_id, description="desc", body="- do the thing"):
    skill_dir = os.path.join(root, skill_id)
    os.makedirs(skill_dir, exist_ok=True)
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(
            f"---\nname: {skill_id}\ndescription: \"{description}\"\n---\n\n"
            f"<!-- gate:begin -->\n{body}\n<!-- gate:end -->\n"
        )


@pytest.fixture
def skill_dirs(tmp_path, monkeypatch):
    curated = tmp_path / "skills"
    imported = tmp_path / "skills-imported"
    curated.mkdir()
    imported.mkdir()
    monkeypatch.setattr(skills_module, "SKILLS_DIR", str(curated))
    monkeypatch.setattr(skills_module, "IMPORTED_SKILLS_DIR", str(imported))
    return curated, imported


def test_available_skills_include_imported_directory(skill_dirs):
    curated, imported = skill_dirs
    _write_skill(str(curated), "owasp-security")
    _write_skill(str(imported), "my-imported-skill")

    found = {s["id"]: s for s in skills_module.get_available_skills()}

    assert found["owasp-security"]["source"] == "curated"
    assert found["my-imported-skill"]["source"] == "imported"


def test_curated_skill_wins_over_imported_with_same_id(skill_dirs):
    curated, imported = skill_dirs
    _write_skill(str(curated), "devops", description="curated version")
    _write_skill(str(imported), "devops", description="imported version")

    found = [s for s in skills_module.get_available_skills() if s["id"] == "devops"]

    assert len(found) == 1
    assert found[0]["description"] == "curated version"
    assert found[0]["source"] == "curated"


def test_instructions_and_details_resolve_imported_skills(skill_dirs):
    _, imported = skill_dirs
    _write_skill(str(imported), "pdf-forms", body="- always validate the field map")

    instructions = skills_module.get_skill_instructions("pdf-forms")
    details = skills_module.get_skill_details("pdf-forms")

    assert "always validate the field map" in instructions
    assert details["source"] == "imported"


def test_save_imported_skill_writes_file_and_returns_details(skill_dirs):
    _, imported = skill_dirs
    skill_md = '---\nname: scraped\ndescription: "From a repo"\n---\n\nbody text\n'

    saved = skills_module.save_imported_skill("scraped", skill_md, origin="https://github.com/o/r")

    assert os.path.isfile(os.path.join(str(imported), "scraped", "SKILL.md"))
    assert saved["id"] == "scraped"
    assert saved["source"] == "imported"
    assert saved["origin"] == "https://github.com/o/r"


def test_save_imported_skill_rejects_unsafe_id(skill_dirs):
    with pytest.raises(ValueError):
        skills_module.save_imported_skill("../escape", "---\nname: x\n---\nbody")


def test_save_imported_skill_rejects_existing_id_without_overwrite(skill_dirs):
    curated, imported = skill_dirs
    _write_skill(str(curated), "devops")
    _write_skill(str(imported), "already-here")

    with pytest.raises(ValueError):
        skills_module.save_imported_skill("devops", "---\nname: devops\n---\nbody")
    with pytest.raises(ValueError):
        skills_module.save_imported_skill("already-here", "---\nname: already-here\n---\nbody")

    skills_module.save_imported_skill("already-here", "---\nname: already-here\ndescription: \"new\"\n---\nbody", overwrite=True)
    assert skills_module.get_skill_details("already-here")["description"] == "new"


def test_delete_imported_skill_only_removes_imported(skill_dirs):
    curated, imported = skill_dirs
    _write_skill(str(curated), "devops")
    _write_skill(str(imported), "throwaway")

    skills_module.delete_imported_skill("throwaway")
    assert not os.path.exists(os.path.join(str(imported), "throwaway"))

    with pytest.raises(ValueError):
        skills_module.delete_imported_skill("devops")
    assert os.path.isfile(os.path.join(str(curated), "devops", "SKILL.md"))
