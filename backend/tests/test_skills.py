import pytest
from backend.skills import (
    get_available_skills,
    get_skill_instructions,
    parse_model_identifier,
    SKILL_METADATA,
)
from backend.pricing import get_model_pricing


def test_parse_model_identifier():
    base, skill = parse_model_identifier("local/qwen3.6-27b")
    assert base == "local/qwen3.6-27b"
    assert skill is None

    base, skill = parse_model_identifier("local/qwen3.6-27b@owasp-security")
    assert base == "local/qwen3.6-27b"
    assert skill == "owasp-security"

    base, skill = parse_model_identifier("openai/gpt-4o@karpathy-guidelines")
    assert base == "openai/gpt-4o"
    assert skill == "karpathy-guidelines"


def test_get_available_skills():
    skills = get_available_skills()
    assert isinstance(skills, list)
    assert len(skills) > 0
    # Check that curated skills have their metadata populated
    for skill in skills:
        assert "id" in skill
        assert "title" in skill
        assert "badge" in skill
        if skill["id"] in SKILL_METADATA:
            assert skill["title"] == SKILL_METADATA[skill["id"]]["title"]
            assert skill["badge"] == SKILL_METADATA[skill["id"]]["badge"]


def test_pricing_strips_skill_suffix():
    base_pricing = get_model_pricing("local/qwen3.6-27b")
    skill_pricing = get_model_pricing("local/qwen3.6-27b@owasp-security")
    assert base_pricing == skill_pricing
    assert skill_pricing["input"] == 0.0
    assert skill_pricing["output"] == 0.0


def test_skill_instructions_content():
    instructions = get_skill_instructions("owasp-security")
    assert "SPECIALIZED COUNCIL ROLE: SECURITY AUDITOR" in instructions
    assert "Security Auditor" in instructions
    assert "rigorously enforce" in instructions
