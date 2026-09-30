"""Built-in tool implementations for LLM Council autonomous agents.

Provides high-leverage tools for:
- Web Search (DuckDuckGo Lite)
- Web Fetch & Content Extraction
- GitHub & Package Registry Scouting
- Local Workspace Code Inspection (Read, Git Diff, Graph Queries)
- Vault / Architectural Memory Search
"""

import asyncio
import html
import os
import re
from pathlib import Path
from typing import Optional

import httpx

from ..netguard import DEFAULT_CONTENT_TYPES, BlockedURL, safe_get
from ..research import (
    search_web,
    search_github_repositories,
    search_package_ecosystem,
)
from . import webcontent
from .search import searxng_search


PDF_MAX_BYTES = 10_000_000


async def tool_web_search(query: str, limit: int = 5) -> str:
    """Search the web for up-to-date documentation, RFCs, articles, or benchmark comparisons.

    Args:
        query: Specific search query terms
        limit: Maximum number of search results to return (1-8, default 5)
    """
    try:
        limit = max(1, min(8, int(limit)))
        # Self-hosted SearXNG first; legacy HN/DDG search only when it is unset or down.
        results = await searxng_search(query, limit=limit)
        if not results:
            results = await search_web(query, limit=limit)
        if not results:
            return f"No web search results found for query: '{query}'."

        formatted = [f"### Web Search Results for: {query}\n"]
        for i, item in enumerate(results, 1):
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            desc = item.get("description", "")
            formatted.append(f"{i}. **[{title}]({url})**\n   {desc}\n")

        return "\n".join(formatted)
    except Exception as e:
        return f"Error executing web search: {str(e)}"


async def tool_web_fetch(url: str, max_chars: int = 6000, start_index: int = 0) -> str:
    """Fetch a URL and return clean markdown (HTML pages, PDFs and text are supported).

    Long pages are paged: pass the `start_index` printed in the truncation note to continue.

    Args:
        url: Full HTTP or HTTPS URL to fetch
        max_chars: Maximum characters to return per call (500-20000, default 6000)
        start_index: Character offset to start from, for reading past a truncation
    """
    try:
        max_chars = max(500, min(20000, int(max_chars)))
        start_index = max(0, int(start_index))
    except (TypeError, ValueError):
        return "Error: max_chars and start_index must be integers."

    cached = webcontent.cache_get(url)
    if cached is None:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain;q=0.9,*/*;q=0.8",
            }
            resp, body = await safe_get(
                url, headers=headers, max_bytes=PDF_MAX_BYTES,
                content_types=DEFAULT_CONTENT_TYPES + ("application/pdf",),
            )
            if resp.status_code != 200:
                return f"Failed to fetch URL {url}: HTTP {resp.status_code}"
            ctype = resp.headers.get("content-type", "")
            is_pdf = ctype.split(";")[0].strip().lower() == "application/pdf"
            if len(body) >= PDF_MAX_BYTES and is_pdf:
                return f"Error: PDF at {url} is larger than {PDF_MAX_BYTES // 1_000_000} MB."
            cached = await webcontent.extract(body, ctype, resp.charset_encoding, url)
            webcontent.cache_put(url, cached)
        except BlockedURL as e:
            return f"Error: URL blocked ({e})"
        except ValueError as e:
            return f"Error reading {url}: {e}"
        except Exception as e:
            return f"Error fetching URL {url}: {type(e).__name__}"

    title, text = cached
    total = len(text)
    if total == 0:
        return f"### Content from: {url}\n\n(The page has no readable text.)"
    if start_index >= total:
        return f"### Content from: {url}\n\nstart_index {start_index} is past the end ({total} characters)."

    chunk = text[start_index:start_index + max_chars]
    end = start_index + len(chunk)
    head = f"### Content from: {url}\n" + (f"Title: {title}\n" if title else "")
    head += f"Characters {start_index}-{end} of {total}\n\n"
    note = ""
    if end < total:
        note = f"\n\n[... truncated. Call web_fetch again with start_index={end} to continue ...]"
    return head + chunk + note


async def tool_github_scout(query_or_repo: str) -> str:
    """Scout GitHub for repositories, evaluate production readiness, license, stars, and README.

    Args:
        query_or_repo: Either an 'owner/repo' path (e.g. 'pallets/flask') or a search query (e.g. 'sqlite vector search')
    """
    try:
        clean = query_or_repo.strip().strip("/")
        # Check if direct owner/repo format
        parts = clean.split("/")
        if len(parts) == 2 and " " not in clean:
            owner, repo = parts[0], parts[1]
            try:
                headers = {
                    "User-Agent": "LLM-Council-Research/1.0",
                    "Accept": "application/vnd.github.v3+json",
                }
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        stars = data.get("stargazers_count", 0)
                        forks = data.get("forks_count", 0)
                        lic = (data.get("license") or {}).get("name", "Unknown")
                        desc = data.get("description", "")
                        url = data.get("html_url", f"https://github.com/{owner}/{repo}")
                        return (
                            f"### GitHub Repository: {owner}/{repo}\n"
                            f"- **URL:** {url}\n"
                            f"- **Stars:** {stars:,} | **Forks:** {forks:,}\n"
                            f"- **License:** {lic}\n"
                            f"- **Description:** {desc}"
                        )
            except Exception:
                pass

        # Fallback to repository search
        results = await search_github_repositories(clean, limit=4)
        if not results:
            return f"No GitHub repositories found matching '{clean}'."

        output = [f"### Top GitHub Candidates for: '{clean}'\n"]
        for r in results:
            title = r.get("title", "")
            url = r.get("url", "")
            desc = r.get("description", "")
            stars = r.get("stars", 0)
            lic = r.get("license", "Unknown")
            output.append(f"- **[{title}]({url})** (★ {stars:,} | License: {lic})\n  {desc}\n")

        return "\n".join(output)
    except Exception as e:
        return f"Error scouting GitHub: {str(e)}"


async def tool_package_scout(package_query: str) -> str:
    """Search PyPI and NPM package registries for packages, versions, and dependencies.

    Args:
        package_query: Package name or keyword (e.g. 'chromadb', 'fastapi', 'zod')
    """
    try:
        results = await search_package_ecosystem(package_query, limit=5)
        if not results:
            return f"No packages found matching '{package_query}'."

        output = [f"### Package Registry Results for: '{package_query}'\n"]
        for r in results:
            title = r.get("title", "")
            eco = r.get("ecosystem", "").upper()
            version = r.get("version", "")
            lic = r.get("license", "Not specified")
            desc = r.get("description", "")
            url = r.get("url", "")
            output.append(f"- **[{title}]({url})** [{eco}] (v{version} | {lic})\n  {desc}\n")

        return "\n".join(output)
    except Exception as e:
        return f"Error scouting packages: {str(e)}"


_DENY_NAMES = {".env", ".netrc", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "providers.json", "credentials"}
_DENY_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".crt")
_DENY_DIRS = {".git", ".ssh", ".aws", ".gnupg", "data", "node_modules"}


def _workspace_roots() -> list:
    roots = [Path("/app/workspace"), Path(os.path.expanduser("~/workspace"))]
    return [r.resolve() for r in roots if r.is_dir()]


def _is_denied(path: Path) -> bool:
    """Secrets and runtime data that a model must never read, wherever they sit."""
    name = path.name.lower()
    if name in _DENY_NAMES or name.startswith(".env") or name.endswith(_DENY_SUFFIXES):
        return True
    return any(part.lower() in _DENY_DIRS for part in path.parts[:-1])


def resolve_workspace_file(file_path: str, target_workspace: Optional[str] = None) -> Path:
    """Resolve file_path inside a workspace root or raise PermissionError/FileNotFoundError."""
    if target_workspace and (Path(target_workspace).name != target_workspace or target_workspace in (".", "..")):
        raise PermissionError("target_workspace must be a single directory name")
    roots = _workspace_roots()
    if not roots:
        raise FileNotFoundError("no workspace is mounted")

    p = Path(file_path)
    if p.is_absolute():
        candidates = [p]
    else:
        candidates = [(r / target_workspace if target_workspace else r) / p for r in roots]

    for cand in candidates:
        resolved = cand.resolve()
        if not any(resolved.is_relative_to(r) for r in roots):
            raise PermissionError("path is outside the workspace")
        if _is_denied(resolved):
            raise PermissionError("access to this file is not allowed")
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(file_path)


async def tool_workspace_read_file(file_path: str, target_workspace: Optional[str] = None, max_lines: int = 150) -> str:
    """Read a code file from the current project or workspace for architecture/security review.

    Args:
        file_path: Path relative to the workspace (absolute paths must stay inside it)
        target_workspace: Optional workspace directory name (e.g. 'dev-agent-kit')
        max_lines: Max lines to return (default 150)
    """
    try:
        max_lines = max(1, min(int(max_lines), 500))
        resolved_path = resolve_workspace_file(file_path, target_workspace)
        with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines + 1)]
        lines = [ln for ln in lines if ln]

        is_truncated = len(lines) > max_lines
        content = "".join(lines[:max_lines])
        header = f"### File: {file_path} ({len(lines[:max_lines])} lines)\n```\n"
        footer = "\n```" + ("\n[... Truncated remaining lines ...]" if is_truncated else "")
        return header + content + footer
    except PermissionError as e:
        return f"Error: cannot read {file_path} ({e})"
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"Error reading workspace file {file_path}: {str(e)}"


async def tool_workspace_git_diff(target_workspace: Optional[str] = None, max_chars: int = 3500) -> str:
    """Inspect current git diff and changed files in the workspace.

    Args:
        target_workspace: Optional workspace directory name (e.g. 'dev-agent-kit')
        max_chars: Max characters of diff to return (default 3500)
    """
    try:
        base_dir = "/app/workspace" if os.path.exists("/app/workspace") else os.path.expanduser("~/workspace")
        if target_workspace:
            if Path(target_workspace).name != target_workspace or target_workspace in (".", ".."):
                return "Error: target_workspace must be a single directory name"
            base_dir = os.path.join(base_dir, target_workspace)

        proc = await asyncio.create_subprocess_exec(
            "git", "status", "-s",
            cwd=base_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        status_output = stdout.decode("utf-8", errors="replace").strip()

        proc_diff = await asyncio.create_subprocess_exec(
            "git", "diff", "--stat",
            cwd=base_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        diff_out, _ = await proc_diff.communicate()
        stat_output = diff_out.decode("utf-8", errors="replace").strip()

        proc_full = await asyncio.create_subprocess_exec(
            "git", "diff",
            cwd=base_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        full_diff, _ = await proc_full.communicate()
        full_text = full_diff.decode("utf-8", errors="replace")
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + f"\n\n[... Truncated to {max_chars} chars ...]"

        res = [f"### Git Status & Diff ({target_workspace or 'Workspace'})\n"]
        if status_output:
            res.append(f"**Changed Files:**\n```\n{status_output}\n```\n")
        if stat_output:
            res.append(f"**Summary Stat:**\n```\n{stat_output}\n```\n")
        if full_text.strip():
            res.append(f"**Diff:**\n```diff\n{full_text}\n```")
        else:
            res.append("Clean working tree (no uncommitted diff).")

        return "\n".join(res)
    except Exception as e:
        return f"Error executing git diff: {str(e)}"
