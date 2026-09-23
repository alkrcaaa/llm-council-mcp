"""Tests for importing skills from a GitHub URL or pasted markdown."""

import asyncio
import pytest

from backend import skill_import


def run(coro):
    return asyncio.run(coro)


# --- URL resolution -------------------------------------------------------

def test_repo_url_tries_skill_md_then_readme_on_main_and_master():
    candidates = skill_import.resolve_candidate_urls("https://github.com/owner/my-repo")

    assert candidates == [
        "https://raw.githubusercontent.com/owner/my-repo/main/SKILL.md",
        "https://raw.githubusercontent.com/owner/my-repo/main/README.md",
        "https://raw.githubusercontent.com/owner/my-repo/master/SKILL.md",
        "https://raw.githubusercontent.com/owner/my-repo/master/README.md",
    ]


def test_blob_url_maps_to_single_raw_file():
    candidates = skill_import.resolve_candidate_urls(
        "https://github.com/owner/repo/blob/v2/skills/pdf/SKILL.md"
    )

    assert candidates == [
        "https://raw.githubusercontent.com/owner/repo/v2/skills/pdf/SKILL.md"
    ]


def test_tree_url_looks_for_skill_md_then_readme_in_that_directory():
    candidates = skill_import.resolve_candidate_urls(
        "https://github.com/owner/repo/tree/main/skills/pdf-forms"
    )

    assert candidates == [
        "https://raw.githubusercontent.com/owner/repo/main/skills/pdf-forms/SKILL.md",
        "https://raw.githubusercontent.com/owner/repo/main/skills/pdf-forms/README.md",
    ]


def test_raw_url_is_used_as_is():
    url = "https://raw.githubusercontent.com/owner/repo/main/SKILL.md"
    assert skill_import.resolve_candidate_urls(url) == [url]


def test_non_http_url_is_rejected():
    with pytest.raises(ValueError):
        skill_import.resolve_candidate_urls("file:///etc/passwd")


def test_suggested_id_comes_from_directory_then_repo_name():
    assert skill_import.suggest_skill_id(
        "https://github.com/owner/repo/tree/main/skills/PDF_Forms"
    ) == "pdf-forms"
    assert skill_import.suggest_skill_id("https://github.com/owner/Awesome.Skill") == "awesome-skill"
    assert skill_import.suggest_skill_id(
        "https://github.com/owner/repo/blob/main/skills/deep-research/SKILL.md"
    ) == "deep-research"


# --- normalization --------------------------------------------------------

SKILL_MD = '---\nname: ready-made\ndescription: "Already a skill"\n---\n\n<!-- gate:begin -->\n- rule one\n<!-- gate:end -->\n'
README_MD = "# Cool Tool\n\nIt converts spreadsheets into reports.\n\n## Usage\n\nRun it.\n"


def test_existing_skill_md_is_passed_through_untouched():
    result = run(skill_import.prepare_skill(markdown=SKILL_MD))

    assert result["method"] == "passthrough"
    assert result["id"] == "ready-made"
    assert result["skill_md"] == SKILL_MD
    assert "rule one" in result["checklist"]


def test_readme_is_normalized_by_the_llm(monkeypatch):
    generated = (
        '---\nname: cool-tool\ndescription: "Turns spreadsheets into reports"\n---\n\n'
        "<!-- gate:begin -->\n- verify the sheet schema first\n<!-- gate:end -->\n"
    )

    async def fake_query_model(model, messages, timeout=120.0):
        assert "Cool Tool" in messages[-1]["content"]
        return {"content": f"```markdown\n{generated}```"}

    monkeypatch.setattr(skill_import, "query_model", fake_query_model)

    result = run(skill_import.prepare_skill(markdown=README_MD, skill_id="cool-tool"))

    assert result["method"] == "llm"
    assert result["id"] == "cool-tool"
    assert result["description"] == "Turns spreadsheets into reports"
    assert "verify the sheet schema first" in result["checklist"]


def test_normalizer_model_defaults_to_the_configured_chairman(monkeypatch):
    monkeypatch.delenv("SKILL_NORMALIZER_MODEL", raising=False)
    monkeypatch.setattr(skill_import, "get_chairman_model", lambda: "local/claude-code")

    assert skill_import.get_normalizer_model() == "local/claude-code"


def test_normalizer_model_can_be_overridden_by_env(monkeypatch):
    monkeypatch.setenv("SKILL_NORMALIZER_MODEL", "custom/groq")

    assert skill_import.get_normalizer_model() == "custom/groq"


def test_normalizer_model_falls_back_when_no_chairman_is_configured(monkeypatch):
    monkeypatch.delenv("SKILL_NORMALIZER_MODEL", raising=False)

    def broken_chairman():
        raise RuntimeError("no config")

    monkeypatch.setattr(skill_import, "get_chairman_model", broken_chairman)

    assert skill_import.get_normalizer_model() == skill_import.FALLBACK_NORMALIZER_MODEL


def test_normalization_queries_the_configured_model(monkeypatch):
    used = {}

    async def fake_query_model(model, messages, timeout=120.0):
        used["model"] = model
        return {"content": '---\nname: cool-tool\ndescription: "x"\n---\n\nbody\n'}

    monkeypatch.delenv("SKILL_NORMALIZER_MODEL", raising=False)
    monkeypatch.setattr(skill_import, "query_model", fake_query_model)
    monkeypatch.setattr(skill_import, "get_chairman_model", lambda: "local/claude-code")

    run(skill_import.prepare_skill(markdown=README_MD, skill_id="cool-tool"))

    assert used["model"] == "local/claude-code"


def test_falls_back_to_deterministic_frontmatter_when_llm_fails(monkeypatch):
    async def failing_query_model(model, messages, timeout=120.0):
        return None

    monkeypatch.setattr(skill_import, "query_model", failing_query_model)

    result = run(skill_import.prepare_skill(markdown=README_MD, skill_id="cool-tool"))

    assert result["method"] == "fallback"
    assert result["id"] == "cool-tool"
    assert result["description"] == "It converts spreadsheets into reports."
    assert result["skill_md"].startswith("---\nname: cool-tool\n")
    assert "It converts spreadsheets into reports." in result["skill_md"]


def test_llm_output_without_frontmatter_falls_back(monkeypatch):
    async def chatty_query_model(model, messages, timeout=120.0):
        return {"content": "Sure! Here is a nice summary of the skill."}

    monkeypatch.setattr(skill_import, "query_model", chatty_query_model)

    result = run(skill_import.prepare_skill(markdown=README_MD, skill_id="cool-tool"))

    assert result["method"] == "fallback"


def test_fetches_first_reachable_candidate_url(monkeypatch):
    fetched = []

    async def fake_fetch(url):
        fetched.append(url)
        if url.endswith("/main/README.md"):
            return README_MD
        return None

    monkeypatch.setattr(skill_import, "fetch_url", fake_fetch)
    monkeypatch.setattr(skill_import, "normalize_with_llm", lambda *a, **k: _none())

    result = run(skill_import.prepare_skill(url="https://github.com/owner/cool-tool"))

    assert fetched[:2] == [
        "https://raw.githubusercontent.com/owner/cool-tool/main/SKILL.md",
        "https://raw.githubusercontent.com/owner/cool-tool/main/README.md",
    ]
    assert result["origin"] == "https://github.com/owner/cool-tool"
    assert result["source_url"] == "https://raw.githubusercontent.com/owner/cool-tool/main/README.md"
    assert result["id"] == "cool-tool"


async def _none():
    return None


def test_unreachable_url_raises(monkeypatch):
    async def fake_fetch(url):
        return None

    monkeypatch.setattr(skill_import, "fetch_url", fake_fetch)

    with pytest.raises(ValueError):
        run(skill_import.prepare_skill(url="https://github.com/owner/missing"))


def test_requires_url_or_markdown():
    with pytest.raises(ValueError):
        run(skill_import.prepare_skill())
