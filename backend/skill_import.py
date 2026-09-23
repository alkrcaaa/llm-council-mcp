"""Import council skills from a GitHub URL or pasted markdown.

A skill the council can wear is a SKILL.md: YAML frontmatter (name, description)
plus an operative checklist. Most repositories only ship a README, so anything
that is not already a SKILL.md gets normalized -- by a fast model when one is
reachable, deterministically otherwise.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from .config_api import get_chairman_model
from .openrouter import query_model
from .skills import (
    SKILL_METADATA,
    extract_gate_or_summary,
    parse_frontmatter,
)

RAW_HOST = "https://raw.githubusercontent.com"
DEFAULT_BRANCHES = ("main", "master")
SKILL_FILENAMES = ("SKILL.md", "README.md")
# The normalizer runs through whatever provider this deployment actually has,
# so it defaults to the configured chairman instead of a hardcoded OpenRouter model.
FALLBACK_NORMALIZER_MODEL = "google/gemini-2.0-flash-001"
GITHUB_API = "https://api.github.com"
MAX_REPO_SKILLS = 500
FETCH_TIMEOUT = 20.0
MAX_SOURCE_CHARS = 24000
MAX_DESCRIPTION_CHARS = 240

NORMALIZE_PROMPT = """You convert documentation into a SKILL.md file for an LLM council.

A council seat wearing this skill must act as a domain specialist, so the file has to be
operative instructions, not a product description.

Output ONLY the file, with no commentary, in exactly this shape:

---
name: {skill_id}
description: "One sentence, under 200 characters, describing the specialist role."
---

<!-- gate:begin -->
- 5 to 12 imperative rules the specialist must enforce when answering and when
  reviewing peers. Concrete and checkable, drawn from the source document.
<!-- gate:end -->

## Context

A few short paragraphs of the essential domain knowledge from the source.

Source document:
---
{source}
---"""


def _slugify(value: str) -> str:
    """Turn arbitrary text into a safe skill id."""
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug


def _github_parts(url: str) -> Optional[Dict[str, Any]]:
    """Split a github.com URL into owner/repo/kind/ref/path, or None if not GitHub."""
    parsed = urlparse(url)
    if parsed.netloc.lower() not in ("github.com", "www.github.com"):
        return None
    segments = [p for p in parsed.path.split("/") if p]
    if len(segments) < 2:
        raise ValueError("GitHub URL must include an owner and a repository")
    repo = segments[1][:-4] if segments[1].endswith(".git") else segments[1]
    rest = segments[2:]
    kind = rest[0] if rest and rest[0] in ("blob", "tree") else None
    ref = rest[1] if kind and len(rest) > 1 else None
    path = "/".join(rest[2:]) if kind else ""
    return {"owner": segments[0], "repo": repo, "kind": kind, "ref": ref, "path": path}


def resolve_candidate_urls(url: str) -> List[str]:
    """Ordered raw URLs to try for a given source URL."""
    if not url or not isinstance(url, str):
        raise ValueError("A URL is required")
    url = url.strip()

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http(s) URLs can be imported")

    if parsed.netloc.lower() in ("raw.githubusercontent.com", "gist.githubusercontent.com"):
        return [url]

    parts = _github_parts(url)
    if not parts:
        return [url]

    base = f"{RAW_HOST}/{parts['owner']}/{parts['repo']}"
    if parts["kind"] == "blob" and parts["path"]:
        return [f"{base}/{parts['ref']}/{parts['path']}"]
    if parts["kind"] == "tree":
        prefix = f"{base}/{parts['ref']}" + (f"/{parts['path']}" if parts["path"] else "")
        return [f"{prefix}/{name}" for name in SKILL_FILENAMES]
    return [
        f"{base}/{branch}/{name}"
        for branch in DEFAULT_BRANCHES
        for name in SKILL_FILENAMES
    ]


def suggest_skill_id(url: str) -> str:
    """Guess a skill id from a source URL: the containing directory, else the repo."""
    try:
        parts = _github_parts(url)
    except ValueError:
        parts = None

    if parts:
        path_segments = [p for p in (parts["path"] or "").split("/") if p]
        if path_segments:
            last = path_segments[-1]
            if last.lower().endswith(".md"):
                path_segments = path_segments[:-1]
                last = path_segments[-1] if path_segments else re.sub(r"\.md$", "", last, flags=re.I)
            return _slugify(last) or _slugify(parts["repo"])
        return _slugify(parts["repo"])

    segments = [p for p in urlparse(url).path.split("/") if p]
    for segment in reversed(segments):
        if segment.lower().endswith(".md"):
            continue
        slug = _slugify(segment)
        if slug:
            return slug
    return "imported-skill"


async def fetch_url(url: str) -> Optional[str]:
    """Fetch a URL, returning its text or None when it is not reachable."""
    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url)
        if response.status_code == 200 and response.text.strip():
            return response.text
    except Exception:
        return None
    return None


async def fetch_json(url: str) -> Optional[Any]:
    """Fetch a JSON document, returning None when it is not reachable."""
    text = await fetch_url(url)
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


async def list_repo_skills(url: str) -> Dict[str, Any]:
    """List every SKILL.md a GitHub repository holds, for multi-skill collections."""
    parts = _github_parts(url)
    if not parts:
        raise ValueError("Listing skills needs a github.com repository URL")

    owner, repo = parts["owner"], parts["repo"]
    ref = parts["ref"] or DEFAULT_BRANCHES[0]
    subpath = (parts["path"] or "").strip("/")

    tree = await fetch_json(f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{ref}?recursive=1")
    if not tree and not parts["ref"]:
        ref = DEFAULT_BRANCHES[1]
        tree = await fetch_json(f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{ref}?recursive=1")
    if not tree or not isinstance(tree, dict) or "tree" not in tree:
        raise ValueError(f"Could not read the file list of {owner}/{repo}")

    skills: List[Dict[str, str]] = []
    for node in tree.get("tree", []):
        path = node.get("path", "")
        if not path.endswith("SKILL.md"):
            continue
        if subpath and not (path == f"{subpath}/SKILL.md" or path.startswith(f"{subpath}/")):
            continue
        directory = path[: -len("SKILL.md")].strip("/")
        skill_id = _slugify(directory.split("/")[-1]) if directory else _slugify(repo)
        if not skill_id:
            continue
        skills.append({
            "id": skill_id,
            "path": path,
            "raw_url": f"{RAW_HOST}/{owner}/{repo}/{ref}/{path}",
            "origin": f"https://github.com/{owner}/{repo}/tree/{ref}" + (f"/{directory}" if directory else ""),
        })
        if len(skills) >= MAX_REPO_SKILLS:
            break

    return {"repo": f"{owner}/{repo}", "ref": ref, "skills": skills}


INSTALL_COMMAND_RE = re.compile(
    r"^\s*((?:npx\s+skills\s+add|gh\s+skill\s+install)\s+[\w.-]+/[\w.-]+)\s*$",
    re.MULTILINE,
)


def find_install_command(markdown: str) -> Optional[str]:
    """The install command a README advertises, shown to the user as a hint."""
    match = INSTALL_COMMAND_RE.search(markdown or "")
    return " ".join(match.group(1).split()) if match else None


def has_skill_frontmatter(markdown: str) -> bool:
    """True when the markdown is already a SKILL.md (frontmatter with a name)."""
    meta, _ = parse_frontmatter(markdown or "")
    return bool(meta.get("name"))


def first_paragraph(markdown: str) -> str:
    """First prose paragraph, used as a description when nothing better exists."""
    _, body = parse_frontmatter(markdown or "")
    for block in re.split(r"\n\s*\n", body):
        line = block.strip()
        if not line or line.startswith(("#", "<!--", "!", "|", "```", "---", "<")):
            continue
        text = " ".join(line.split())
        if len(text) > MAX_DESCRIPTION_CHARS:
            text = text[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"
        return text
    return ""


def _strip_code_fence(text: str) -> str:
    """Unwrap a ```markdown ... ``` block the model may have added."""
    fenced = re.match(r"^\s*```[a-zA-Z]*\s*\n(.*?)```\s*$", text or "", re.DOTALL)
    return fenced.group(1) if fenced else (text or "").strip()


def _set_frontmatter_name(skill_md: str, skill_id: str) -> str:
    """Force the frontmatter name to match the id the skill is stored under."""
    meta, _ = parse_frontmatter(skill_md)
    if meta.get("name") == skill_id:
        return skill_md
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", skill_md, re.DOTALL)
    if not match:
        return skill_md
    lines = [
        line for line in match.group(1).splitlines()
        if not line.strip().lower().startswith("name:")
    ]
    yaml_text = "\n".join([f"name: {skill_id}"] + lines)
    return f"---\n{yaml_text}\n---\n{skill_md[match.end():]}"


def build_fallback_skill_md(markdown: str, skill_id: str) -> str:
    """Deterministic SKILL.md: frontmatter derived from the text, body preserved."""
    _, body = parse_frontmatter(markdown or "")
    description = first_paragraph(markdown).replace('"', "'")
    return f'---\nname: {skill_id}\ndescription: "{description}"\n---\n\n{body.strip()}\n'


def get_normalizer_model() -> str:
    """Model used to rewrite documentation into a SKILL.md."""
    override = os.getenv("SKILL_NORMALIZER_MODEL", "").strip()
    if override:
        return override
    try:
        chairman = get_chairman_model()
    except Exception:
        chairman = None
    return chairman or FALLBACK_NORMALIZER_MODEL


async def normalize_with_llm(markdown: str, skill_id: str) -> Optional[str]:
    """Ask a model to rewrite documentation as a SKILL.md. None if it can't."""
    prompt = NORMALIZE_PROMPT.format(skill_id=skill_id, source=(markdown or "")[:MAX_SOURCE_CHARS])
    try:
        result = await query_model(get_normalizer_model(), [{"role": "user", "content": prompt}])
    except Exception:
        return None
    if not result or not result.get("content"):
        return None

    candidate = _strip_code_fence(result["content"])
    if not has_skill_frontmatter(candidate):
        return None
    return candidate


async def prepare_skill(
    url: Optional[str] = None,
    markdown: Optional[str] = None,
    skill_id: Optional[str] = None,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Fetch and/or normalize a skill, returning a preview without writing anything."""
    origin: Optional[str] = None
    source_url: Optional[str] = None
    content: Optional[str] = markdown

    if url and url.strip():
        origin = url.strip()
        for candidate in resolve_candidate_urls(origin):
            fetched = await fetch_url(candidate)
            if fetched and fetched.strip():
                content = fetched
                source_url = candidate
                break
        if not content:
            raise ValueError(f"No SKILL.md or README.md could be fetched from {origin}")
        if not skill_id:
            skill_id = suggest_skill_id(origin)

    if not content or not content.strip():
        raise ValueError("Provide a GitHub URL or paste the skill markdown")

    if has_skill_frontmatter(content):
        method = "passthrough"
        meta, _ = parse_frontmatter(content)
        skill_id = skill_id or _slugify(meta.get("name", "")) or "imported-skill"
        skill_md = content
    else:
        if not skill_id:
            heading = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            skill_id = _slugify(heading.group(1)) if heading else "imported-skill"
        skill_md = await normalize_with_llm(content, skill_id) if use_llm else None
        method = "llm" if skill_md else "fallback"
        if not skill_md:
            skill_md = build_fallback_skill_md(content, skill_id)

    if method != "passthrough":
        skill_md = _set_frontmatter_name(skill_md, skill_id)

    meta, body = parse_frontmatter(skill_md)
    curated = SKILL_METADATA.get(skill_id, {})
    return {
        "id": skill_id,
        "title": curated.get("title", skill_id.replace("-", " ").title()),
        "description": meta.get("description", ""),
        "checklist": extract_gate_or_summary(body),
        "skill_md": skill_md,
        "origin": origin,
        "source_url": source_url,
        "method": method,
    }
