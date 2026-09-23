"""Skills integration module for LLM Council.

Discovers and parses domain skills from dev-agent-kit / ~/.gemini/config/skills,
providing specialized persona prompts and validation checklists for council seats.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Path where skills are mounted inside container or local host
if os.path.exists("/app/skills"):
    SKILLS_DIR = "/app/skills"
else:
    SKILLS_DIR = os.getenv("SKILLS_DIR", os.path.expanduser("~/.gemini/config/skills"))
    if not os.path.exists(SKILLS_DIR):
        fallback = os.path.expanduser("~/.gemini/config/skills")
        if os.path.exists(fallback):
            SKILLS_DIR = fallback

# Writable directory for skills imported at runtime (GitHub URL / pasted markdown).
# The curated library above stays read-only; everything the UI creates lands here.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if os.path.exists("/app/skills-imported"):
    IMPORTED_SKILLS_DIR = "/app/skills-imported"
else:
    IMPORTED_SKILLS_DIR = os.getenv(
        "IMPORTED_SKILLS_DIR", str(_REPO_ROOT / "skills-imported")
    )

SOURCE_CURATED = "curated"
SOURCE_IMPORTED = "imported"

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


def _skill_dirs() -> List[Tuple[str, str]]:
    """Directories scanned for skills, curated library first."""
    return [(SKILLS_DIR, SOURCE_CURATED), (IMPORTED_SKILLS_DIR, SOURCE_IMPORTED)]


_NEW_SKILL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def is_path_safe_skill_id(skill_id: Any) -> bool:
    """Reject ids that could escape the skills directories."""
    if not skill_id or not isinstance(skill_id, str):
        return False
    if os.path.isabs(skill_id):
        return False
    return not any(part in skill_id for part in ("..", "/", "\\", "\0"))


def require_new_skill_id(skill_id: Any) -> str:
    """Validate an id supplied by a user before it becomes a directory name."""
    if not is_path_safe_skill_id(skill_id) or not _NEW_SKILL_ID_RE.match(skill_id):
        raise ValueError(
            f"Invalid skill id: {skill_id!r}. Use lowercase letters, digits, '-', '_' or '.'"
        )
    return skill_id


def resolve_skill_file(skill_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Locate a skill's SKILL.md, returning (path, source). Curated wins on conflict."""
    if not is_path_safe_skill_id(skill_id):
        return None, None
    for root, source in _skill_dirs():
        candidate = os.path.join(root, skill_id, "SKILL.md")
        if os.path.isfile(candidate):
            return candidate, source
    return None, None


def _summarize_skill(skill_id: str, meta: Dict[str, str], source: str) -> Dict[str, Any]:
    """Merge frontmatter with curated display metadata."""
    curated = SKILL_METADATA.get(skill_id, {})
    return {
        "id": skill_id,
        "title": curated.get("title", skill_id.replace("-", " ").title()),
        "description": meta.get("description", ""),
        "category": curated.get("category", meta.get("category", "General")),
        "badge": curated.get("badge", "SKILL"),
        "source": source,
        "origin": meta.get("origin", ""),
    }


def get_available_skills() -> List[Dict[str, Any]]:
    """Discover all available skills on the system."""
    skills = []
    seen = set()

    for root, source in _skill_dirs():
        if not os.path.isdir(root):
            continue
        for item in sorted(os.listdir(root)):
            skill_file = os.path.join(root, item, "SKILL.md")
            if not os.path.isfile(skill_file):
                continue
            try:
                with open(skill_file, "r", encoding="utf-8") as f:
                    content = f.read()
                meta, _ = parse_frontmatter(content)
                skill_id = meta.get("name", item)
                if skill_id in seen:
                    continue
                seen.add(skill_id)
                skills.append(_summarize_skill(skill_id, meta, source))
            except Exception:
                continue

    return skills


def get_skill_instructions(skill_id: str) -> Optional[str]:
    """Retrieve full operative instructions for a skill to inject into prompts."""
    skill_file, _ = resolve_skill_file(skill_id)
    if not skill_file:
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


def get_skill_details(skill_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full skill documentation, metadata, and guidelines."""
    skill_file, source = resolve_skill_file(skill_id)
    if not skill_file:
        return None

    try:
        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()
        meta, body = parse_frontmatter(content)
        guidelines = extract_gate_or_summary(body)

        details = _summarize_skill(skill_id, meta, source)
        details.update({
            "guidelines": guidelines,
            "checklist": guidelines,
            "content": content,
            "markdown": body,
        })
        return details
    except Exception:
        return None


def _apply_origin(skill_md: str, origin: Optional[str]) -> str:
    """Record where an imported skill came from, inside its frontmatter."""
    if not origin:
        return skill_md
    meta, body = parse_frontmatter(skill_md)
    if not meta or meta.get("origin"):
        return skill_md
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", skill_md, re.DOTALL)
    if not match:
        return skill_md
    yaml_text = match.group(1)
    return f"---\n{yaml_text}\norigin: \"{origin}\"\n---\n{skill_md[match.end():]}"


def save_imported_skill(
    skill_id: str,
    skill_md: str,
    origin: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Write an imported skill into the writable skills directory."""
    require_new_skill_id(skill_id)
    if not skill_md or not skill_md.strip():
        raise ValueError("Skill content is empty")

    existing_file, existing_source = resolve_skill_file(skill_id)
    if existing_file:
        if existing_source == SOURCE_CURATED:
            raise ValueError(
                f"'{skill_id}' already exists in the curated skill library; choose another id"
            )
        if not overwrite:
            raise ValueError(f"Skill '{skill_id}' already exists; enable overwrite to replace it")

    skill_dir = os.path.join(IMPORTED_SKILLS_DIR, skill_id)
    os.makedirs(skill_dir, exist_ok=True)
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(_apply_origin(skill_md, origin))

    return get_skill_details(skill_id)


def delete_imported_skill(skill_id: str) -> None:
    """Remove an imported skill. Curated skills are read-only and never deleted."""
    skill_file, source = resolve_skill_file(skill_id)
    if not skill_file:
        raise ValueError(f"Skill '{skill_id}' not found")
    if source != SOURCE_IMPORTED:
        raise ValueError(f"'{skill_id}' belongs to the read-only skill library and cannot be deleted")
    shutil.rmtree(os.path.dirname(skill_file))


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
