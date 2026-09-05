"""Ingestion and Context Resolution Module for LLM Council.

Discovers local workspace projects and resolves external GitHub repository metadata
and documentation to assemble structured, token-budgeted evaluation dossiers for
council deliberations.
"""

import os
import re
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import httpx

# Workspace root path (inside container or host fallback)
WORKSPACE_ROOT = os.getenv("WORKSPACE_DIR", "/app/workspace")
if not os.path.exists(WORKSPACE_ROOT):
    fallback = os.path.expanduser("~/workspace")
    if os.path.exists(fallback):
        WORKSPACE_ROOT = fallback


def discover_workspaces() -> List[Dict[str, Any]]:
    """Scan the workspace directory for repositories and projects.

    Returns:
        List of project metadata dictionaries with name, path, and available docs.
    """
    projects = []
    if not os.path.isdir(WORKSPACE_ROOT):
        return projects

    for entry in sorted(os.listdir(WORKSPACE_ROOT)):
        full_path = os.path.join(WORKSPACE_ROOT, entry)
        if not os.path.isdir(full_path) or entry.startswith("."):
            continue

        # Check for signature project files
        has_git = os.path.isdir(os.path.join(full_path, ".git"))
        has_claude_md = os.path.isfile(os.path.join(full_path, "CLAUDE.md"))
        has_readme = os.path.isfile(os.path.join(full_path, "README.md"))
        has_pkg = (
            os.path.isfile(os.path.join(full_path, "package.json")) or
            os.path.isfile(os.path.join(full_path, "pyproject.toml")) or
            os.path.isfile(os.path.join(full_path, "Cargo.toml"))
        )

        if has_git or has_claude_md or has_readme or has_pkg:
            # Read first 150 chars of README or CLAUDE.md for description
            desc = ""
            doc_file = os.path.join(full_path, "CLAUDE.md") if has_claude_md else os.path.join(full_path, "README.md")
            if os.path.isfile(doc_file):
                try:
                    with open(doc_file, "r", encoding="utf-8", errors="ignore") as f:
                        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith(("#", "<!--"))]
                        if lines:
                            desc = lines[0][:160]
                except Exception:
                    pass

            projects.append({
                "name": entry,
                "path": full_path,
                "has_claude_md": has_claude_md,
                "has_readme": has_readme,
                "description": desc or "Local workspace project",
            })

    return projects


def get_workspace_dossier(project_name: str, max_chars: int = 3500) -> Optional[str]:
    """Extract a concise architectural summary of a local workspace project.

    Args:
        project_name: Name of directory under WORKSPACE_ROOT
        max_chars: Maximum character budget for documentation content

    Returns:
        Formatted English dossier string or None if not found.
    """
    if not project_name or not os.path.isdir(WORKSPACE_ROOT):
        return None

    # Resolve project path
    project_dir = os.path.join(WORKSPACE_ROOT, project_name)
    if not os.path.isdir(project_dir):
        # Fuzzy match
        for candidate in os.listdir(WORKSPACE_ROOT):
            if candidate.lower() == project_name.lower():
                project_dir = os.path.join(WORKSPACE_ROOT, candidate)
                project_name = candidate
                break
        else:
            return None

    dossier_parts = [
        f"=== TARGET LOCAL REPOSITORY: {project_name} ===",
        f"Location: {project_dir}",
    ]

    # Check for skills in dev-agent-kit or project
    skills_dir = os.path.join(project_dir, "claude", "skills")
    if os.path.isdir(skills_dir):
        skills = [s for s in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, s))]
        if skills:
            dossier_parts.append(f"Registered Domain Skills ({len(skills)}): {', '.join(sorted(skills))}")

    # Inspect tree structure (depth 2, ignoring noise)
    structure_lines = []
    ignored = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", ".code-review-graph"}
    try:
        top_items = sorted(os.listdir(project_dir))
        for item in top_items[:18]:
            if item in ignored or item.startswith("."):
                continue
            item_path = os.path.join(project_dir, item)
            if os.path.isdir(item_path):
                structure_lines.append(f"📁 {item}/")
                try:
                    sub_items = [s for s in sorted(os.listdir(item_path)) if s not in ignored and not s.startswith(".")][:6]
                    for sub in sub_items:
                        structure_lines.append(f"   └── {sub}")
                except Exception:
                    pass
            else:
                structure_lines.append(f"📄 {item}")
        if structure_lines:
            dossier_parts.append("Directory Skeleton:\n" + "\n".join(structure_lines))
    except Exception:
        pass

    # Read primary architecture documentation
    doc_content = ""
    claude_md = os.path.join(project_dir, "CLAUDE.md")
    readme_md = os.path.join(project_dir, "README.md")
    
    if os.path.isfile(claude_md):
        try:
            with open(claude_md, "r", encoding="utf-8", errors="ignore") as f:
                doc_content = f"--- [From CLAUDE.md] ---\n" + f.read()[:max_chars]
        except Exception:
            pass
    elif os.path.isfile(readme_md):
        try:
            with open(readme_md, "r", encoding="utf-8", errors="ignore") as f:
                doc_content = f"--- [From README.md] ---\n" + f.read()[:max_chars]
        except Exception:
            pass

    if doc_content:
        dossier_parts.append("Project Architecture & Conventions:\n" + doc_content)

    return "\n\n".join(dossier_parts)


def extract_github_repos(text: str) -> List[Tuple[str, str]]:
    """Find GitHub repository references in text.

    Returns:
        List of (owner, repo) tuples.
    """
    pattern = r"https?://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)"
    matches = re.findall(pattern, text)
    repos = []
    seen = set()
    for owner, repo in matches:
        # Strip trailing punctuation or url artifacts
        clean_repo = repo.rstrip("/.#?").split("/")[0]
        if clean_repo.endswith(".git"):
            clean_repo = clean_repo[:-4]
        key = f"{owner.lower()}/{clean_repo.lower()}"
        if key not in seen and clean_repo not in {"issues", "pulls", "actions", "wiki", "blob", "tree"}:
            seen.add(key)
            repos.append((owner, clean_repo))
    return repos


async def fetch_github_repo_dossier(owner: str, repo: str, max_chars: int = 4000) -> Optional[str]:
    """Fetch repository metadata and primary README from GitHub.

    Args:
        owner: GitHub organization or username
        repo: Repository name
        max_chars: Maximum character budget for README content

    Returns:
        Formatted English dossier or None if fetch fails.
    """
    headers = {
        "User-Agent": "LLM-Council-Ingest/1.0",
        "Accept": "application/vnd.github.v3+json",
    }
    
    metadata = {}
    readme_text = ""

    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        # 1. Fetch Repository Metadata
        try:
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            resp = await client.get(api_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                metadata = {
                    "full_name": data.get("full_name", f"{owner}/{repo}"),
                    "description": data.get("description", "No description provided"),
                    "stars": data.get("stargazers_count", 0),
                    "forks": data.get("forks_count", 0),
                    "language": data.get("language", "Unknown"),
                    "license": (data.get("license") or {}).get("spdx_id", "Not specified"),
                    "updated_at": (data.get("updated_at") or "")[:10],
                    "archived": data.get("archived", False),
                }
        except Exception:
            pass

        # 2. Fetch README Content (Raw fallback avoids API token limits)
        raw_urls = [
            f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md",
            f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md",
            f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md",
        ]
        for url in raw_urls:
            try:
                resp = await client.get(url, headers={"User-Agent": "LLM-Council-Ingest/1.0"})
                if resp.status_code == 200 and resp.text:
                    readme_text = resp.text[:max_chars]
                    break
            except Exception:
                continue

    if not metadata and not readme_text:
        return None

    # Format English Dossier
    lines = [
        f"=== EXTERNAL CANDIDATE REPOSITORY: {owner}/{repo} ===",
        f"URL: https://github.com/{owner}/{repo}",
    ]
    if metadata:
        lines.append(
            f"Metrics: ⭐ {metadata.get('stars')} stars | 🍴 {metadata.get('forks')} forks | "
            f"Primary Language: {metadata.get('language')} | License: {metadata.get('license')} | "
            f"Last Active: {metadata.get('updated_at')}"
        )
        if metadata.get("archived"):
            lines.append("⚠️ WARNING: This repository is ARCHIVED by its maintainer.")
        lines.append(f"Description: {metadata.get('description')}")

    if readme_text:
        # Strip long HTML comments or SVGs
        cleaned_readme = re.sub(r"<!--.*?-->", "", readme_text, flags=re.DOTALL).strip()
        lines.append(f"README Summary & Capabilities:\n{cleaned_readme}")

    return "\n\n".join(lines)


async def resolve_evaluation_context(
    prompt: str,
    target_workspace: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """Analyze prompt, fetch GitHub references, and inject target workspace context.

    Args:
        prompt: Raw user query from chat interface
        target_workspace: Optional explicit project name under ~/workspace

    Returns:
        Tuple of (enriched_prompt, metadata_dict)
    """
    discovered_repos = extract_github_repos(prompt)
    
    # Auto-detect mentioned workspace if not explicitly set
    detected_workspace = target_workspace
    if not detected_workspace:
        workspaces = discover_workspaces()
        for ws in workspaces:
            # Check if project name is mentioned as a standalone word
            if re.search(rf"\b{re.escape(ws['name'])}\b", prompt, re.IGNORECASE):
                detected_workspace = ws["name"]
                break

    # If neither GitHub repos nor target workspace are involved, return untouched
    if not discovered_repos and not detected_workspace:
        return prompt, {"enriched": False}

    dossier_sections = []

    # 1. Target Workspace Section
    if detected_workspace:
        ws_dossier = get_workspace_dossier(detected_workspace)
        if ws_dossier:
            dossier_sections.append(ws_dossier)

    # 2. External GitHub Repositories Section
    fetched_urls = []
    if discovered_repos:
        tasks = [fetch_github_repo_dossier(owner, repo) for owner, repo in discovered_repos]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, result in enumerate(results):
            if isinstance(result, str) and result.strip():
                dossier_sections.append(result)
                fetched_urls.append(f"https://github.com/{discovered_repos[idx][0]}/{discovered_repos[idx][1]}")

    if not dossier_sections:
        return prompt, {"enriched": False}

    # Assemble structured system mandate
    header = (
        "#################################################################\n"
        "### AUTOMATED CANDIDATE & ARCHITECTURAL EVALUATION DOSSIER    ###\n"
        "### (Pre-fetched live from local workspace & remote sources)   ###\n"
        "#################################################################\n\n"
    )

    sep = "\n\n-----------------------------------------------------------------\n\n"
    joined_dossiers = sep.join(dossier_sections)

    enriched_prompt = (
        f"{header}"
        f"{joined_dossiers}\n\n"
        f"#################################################################\n"
        f"### USER INQUIRY & INTEGRATION QUESTION                       ###\n"
        f"#################################################################\n\n"
        f"{prompt}"
    )

    return enriched_prompt, {
        "enriched": True,
        "target_workspace": detected_workspace,
        "external_repos": fetched_urls,
    }
