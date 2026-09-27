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

from ..research import (
    search_web,
    search_github_repositories,
    search_package_ecosystem,
)


async def tool_web_search(query: str, limit: int = 5) -> str:
    """Search the web for up-to-date documentation, RFCs, articles, or benchmark comparisons.

    Args:
        query: Specific search query terms
        limit: Maximum number of search results to return (1-8, default 5)
    """
    try:
        limit = max(1, min(8, int(limit)))
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


async def tool_web_fetch(url: str, max_chars: int = 4000) -> str:
    """Fetch content from a webpage URL and extract clean, readable text.

    Args:
        url: Full HTTP or HTTPS URL to fetch
        max_chars: Maximum characters to return (default 4000)
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        return "Error: Invalid URL. Must start with http:// or https://"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        }
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return f"Failed to fetch URL {url}: HTTP {resp.status_code}"

            text = resp.text
            # Remove scripts and styles
            text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<nav[^>]*>.*?</nav>", " ", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<footer[^>]*>.*?</footer>", " ", text, flags=re.DOTALL | re.IGNORECASE)

            # Convert links to markdown
            text = re.sub(
                r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)</a>',
                r"[\2](\1)",
                text,
                flags=re.DOTALL | re.IGNORECASE,
            )
            # Convert headings
            for h in range(1, 6):
                text = re.sub(
                    rf"<h{h}[^>]*>(.*?)</h{h}>",
                    rf"\n{'#' * h} \1\n",
                    text,
                    flags=re.DOTALL | re.IGNORECASE,
                )

            # Strip other tags
            text = re.sub(r"<[^>]+>", " ", text)
            # Unescape HTML entities
            text = html.unescape(text)
            # Clean up whitespace
            text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
            text = re.sub(r"[ \t]+", " ", text).strip()

            if len(text) > max_chars:
                text = text[:max_chars] + f"\n\n[... Truncated to {max_chars} characters ...]"

            return f"### Content from: {url}\n\n{text}"
    except Exception as e:
        return f"Error fetching URL {url}: {str(e)}"


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


async def tool_workspace_read_file(file_path: str, target_workspace: Optional[str] = None, max_lines: int = 150) -> str:
    """Read a code file from the current project or workspace for architecture/security review.

    Args:
        file_path: Relative or absolute path to the file
        target_workspace: Optional workspace directory name (e.g. 'dev-agent-kit')
        max_lines: Max lines to return (default 150)
    """
    try:
        # Resolve candidate paths
        base_dir = Path("/app/workspace") if os.path.exists("/app/workspace") else Path(os.path.expanduser("~/workspace"))
        candidate_paths = []
        p = Path(file_path)
        if p.is_absolute():
            candidate_paths.append(p)
        else:
            if target_workspace:
                candidate_paths.append(base_dir / target_workspace / file_path)
                candidate_paths.append(Path(os.path.expanduser("~/workspace")) / target_workspace / file_path)
            candidate_paths.append(base_dir / file_path)
            candidate_paths.append(Path("/app") / file_path)
            candidate_paths.append(Path(os.path.expanduser("~/workspace")) / file_path)

        resolved_path = None
        for cand in candidate_paths:
            if cand.exists() and cand.is_file():
                resolved_path = cand
                break

        if not resolved_path:
            return f"File not found: {file_path} (checked: {[str(c) for c in candidate_paths[:3]]})"

        with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines + 1)]

        is_truncated = len(lines) > max_lines
        content = "".join(lines[:max_lines])
        header = f"### File: {file_path} ({len(lines[:max_lines])} lines)\n```\n"
        footer = "\n```" + ("\n[... Truncated remaining lines ...]" if is_truncated else "")
        return header + content + footer
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
