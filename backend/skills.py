"""Skills integration module for LLM Council.

Discovers and parses domain skills from dev-agent-kit / ~/.gemini/config/skills,
providing specialized persona prompts and validation checklists for council seats.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Path where skills are mounted inside container or local host
SKILLS_DIR = os.getenv("SKILLS_DIR", "/app/skills")
if not os.path.exists(SKILLS_DIR):
    # Fallback to host location if running outside container
    fallback = os.path.expanduser("~/.gemini/config/skills")
    if os.path.exists(fallback):
        SKILLS_DIR = fallback

# Curated metadata & display titles for core dev-agent-kit skills
SKILL_METADATA: Dict[str, Dict[str, str]] = {
    "owasp-security": {
        "title": "Security Auditor",
        "category": "Security",
        "icon": "shield",
        "badge": "SEC",
    },
    "karpathy-guidelines": {
        "title": "System Architect",
        "category": "Architecture",
        "icon": "box",
        "badge": "ARCH",
    },
    "devops": {
        "title": "DevOps & SRE",
        "category": "Infrastructure",
        "icon": "cloud",
        "badge": "OPS",
    },
    "testing-handbook": {
        "title": "Quality & Verification",
        "category": "Testing",
        "icon": "check-circle",
        "badge": "TEST",
    },
    "differential-review": {
        "title": "Code Reviewer",
        "category": "Review",
        "icon": "git-pull-request",
        "badge": "REV",
    },
    "frontend-design": {
        "title": "Frontend & UI/UX",
        "category": "Frontend",
        "icon": "layout",
        "badge": "UI",
    },
    "design-dna": {
        "title": "Design System Lead",
        "category": "Design",
        "icon": "palette",
        "badge": "DNA",
    },
    "ansible": {
        "title": "Automation & Config",
        "category": "Infrastructure",
        "icon": "terminal",
        "badge": "ANS",
    },
    "static-analysis": {
        "title": "Static Analysis / SAST",
        "category": "Security",
        "icon": "search",
        "badge": "SAST",
    },
    "supply-chain-audit": {
        "title": "Supply Chain & Deps",
        "category": "Security",
        "icon": "package",
        "badge": "SCA",
    },
    "remote-ops": {
        "title": "Remote Systems Ops",
        "category": "Infrastructure",
        "icon": "server",
        "badge": "REM",
    },
    "red-team-reasoning": {
        "title": "Red Team & Logic Auditor",
        "category": "Cognitive",
        "icon": "alert-triangle",
        "badge": "RED",
    },
    "first-principles": {
        "title": "First-Principles Thinker",
        "category": "Reasoning",
        "icon": "zap",
        "badge": "BASE",
    },
    "deep-research": {
        "title": "Deep Research & Evidence",
        "category": "Research",
        "icon": "book-open",
        "badge": "RES",
    },
}


def parse_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """Parse YAML frontmatter from markdown content."""
    meta = {}
    body = content
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if match:
        yaml_text, body = match.group(1), match.group(2)
        for line in yaml_text.splitlines():
            line = line.strip()
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip().strip("\"'")
    return meta, body


def extract_gate_or_summary(body: str) -> str:
    """Extract operative checklist within <!-- gate:begin --> or first sections."""
    gate_match = re.search(r"<!--\s*gate:begin\s*-->(.*?)<!--\s*gate:end\s*-->", body, re.DOTALL)
    if gate_match:
        return gate_match.group(1).strip()
    
    # Fallback: first 50 lines before Depth/Links
    lines = []
    for line in body.splitlines():
        if line.startswith("## Depth") or line.startswith("## Resources"):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def get_available_skills() -> List[Dict[str, Any]]:
    """Discover all available skills on the system."""
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills

    for item in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, item)
        skill_file = os.path.join(skill_dir, "SKILL.md")
        if os.path.isdir(skill_dir) and os.path.isfile(skill_file):
            try:
                with open(skill_file, "r", encoding="utf-8") as f:
                    content = f.read()
                meta, body = parse_frontmatter(content)
                skill_id = meta.get("name", item)
                description = meta.get("description", "")
                
                curated = SKILL_METADATA.get(skill_id, {})
                title = curated.get("title", skill_id.replace("-", " ").title())
                category = curated.get("category", "General")
                badge = curated.get("badge", "SKILL")

                skills.append({
                    "id": skill_id,
                    "title": title,
                    "description": description,
                    "category": category,
                    "badge": badge,
                })
            except Exception as e:
                continue

    return skills


def get_skill_instructions(skill_id: str) -> Optional[str]:
    """Retrieve full operative instructions for a skill to inject into prompts."""
    if not skill_id:
        return None

    skill_file = os.path.join(SKILLS_DIR, skill_id, "SKILL.md")
    if not os.path.isfile(skill_file):
        return None

    try:
        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()
        meta, body = parse_frontmatter(content)
        guidelines = extract_gate_or_summary(body)
        
        curated = SKILL_METADATA.get(skill_id, {})
        title = curated.get("title", skill_id.replace("-", " ").title())

        prompt = (
            f"=== SPECIALIZED COUNCIL ROLE: {title.upper()} ({skill_id}) ===\n"
            f"You are participating in this deliberation specifically as the {title} specialist.\n"
            f"Your perspective, analysis, critiques, and solutions MUST strictly prioritize and uphold "
            f"the following core principles and operative standards:\n\n"
            f"{guidelines}\n\n"
            f"When delivering your viewpoint and evaluating peer proposals, rigorously enforce these domain standards."
        )
        return prompt
    except Exception:
        return None


def parse_model_identifier(identifier: str) -> Tuple[str, Optional[str]]:
    """Parse 'model@skill' syntax into (base_model, skill_id).
    
    Examples:
        'local/qwen3.6-27b@owasp-security' -> ('local/qwen3.6-27b', 'owasp-security')
        'local/antigravity' -> ('local/antigravity', None)
    """
    if "@" in identifier:
        base_model, skill_id = identifier.split("@", 1)
        return base_model.strip(), skill_id.strip()
    return identifier.strip(), None


def format_seat_label(identifier: str) -> str:
    """Format human-readable label for a council seat with model and skill."""
    base_model, skill_id = parse_model_identifier(identifier)
    model_name = base_model.split("/")[-1]
    if skill_id:
        curated = SKILL_METADATA.get(skill_id, {})
        skill_title = curated.get("title", skill_id.replace("-", " ").title())
        return f"{model_name} ({skill_title})"
    return model_name
