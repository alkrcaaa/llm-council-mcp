"""Research and Discovery Engine for LLM Council.

Provides automated technology scouting, GitHub repository discovery, web search,
and local skill exploration to ground council deliberations in real-world candidates
rather than latent model hallucination.
"""

import os
import re
import json
import asyncio
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import httpx

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Skills directory configuration (inside container or host)
SKILLS_DIR = os.getenv("SKILLS_DIR", "/app/skills")
if not os.path.isdir(SKILLS_DIR):
    fallback_skills = os.path.expanduser("~/.gemini/config/skills")
    if os.path.isdir(fallback_skills):
        SKILLS_DIR = fallback_skills


# Keywords that trigger automated research scouting
RESEARCH_TRIGGER_PATTERNS = [
    r"\b(araştır|araştırın|araştırma|keşfet|bul|listele|tara)\b",
    r"\b(research|discover|scout|explore|find|look for|search for)\b",
    r"\b(en iyi|alternatifler|neler var|hangileri)\b",
    r"\b(best|alternatives|top|recommended|comparison of)\b",
    r"\b(mcp|mcpleri|mcps|skill|skills|skillset|skillseti|tool|tools)\b",
]


def is_research_query(prompt: str) -> bool:
    """Determine if a prompt represents an exploratory research or scouting question.

    Args:
        prompt: User input question or instruction

    Returns:
        True if the prompt asks to research, discover, or find candidate tools/skills.
    """
    if not prompt or len(prompt.strip()) < 5:
        return False

    text = prompt.lower()
    matches = 0
    for pattern in RESEARCH_TRIGGER_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            matches += 1

    # If at least two trigger categories match (e.g. "araştır" + "mcp" or "best" + "skills")
    return matches >= 2


def extract_search_terms(prompt: str) -> str:
    """Extract clean keywords from a user query suitable for search engines.

    Strips filler words, question marks, and action prefixes.
    """
    cleaned = re.sub(r"[?!.,;:\"']", " ", prompt)
    stop_words = {
        "lütfen", "bana", "için", "hakkında", "nelerdir", "neler", "var", "olan",
        "bir", "ve", "ile", "veya", "en", "iyi", "en iyi", "öner", "bul", "araştır",
        "please", "for", "about", "what", "which", "are", "the", "a", "an", "and",
        "with", "best", "top", "find", "recommend", "show", "me", "tell", "give"
    }
    words = [w for w in cleaned.split() if len(w) > 2 and w.lower() not in stop_words]
    return " ".join(words[:6]) if words else prompt[:40]


async def search_github_repositories(
    query: str,
    limit: int = 5,
    client: Optional[httpx.AsyncClient] = None
) -> List[Dict[str, Any]]:
    """Search public GitHub repositories for libraries, tools, or MCP servers.

    Args:
        query: Search keywords (e.g. "obsidian mcp server")
        limit: Max repositories to return
        client: Optional shared httpx AsyncClient

    Returns:
        List of repository metadata dicts.
    """
    if not query.strip():
        return []

    headers = {
        "User-Agent": "LLM-Council-Research/1.0",
        "Accept": "application/vnd.github.v3+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    encoded_q = urllib.parse.quote(query.strip())
    url = f"{GITHUB_API_BASE}/search/repositories?q={encoded_q}&sort=stars&order=desc&per_page={limit}"

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=8.0)
        should_close = True

    results = []
    try:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", [])[:limit]:
                license_info = item.get("license") or {}
                results.append({
                    "source": "github",
                    "title": item.get("full_name", ""),
                    "url": item.get("html_url", ""),
                    "description": item.get("description") or "No description provided.",
                    "stars": item.get("stargazers_count", 0),
                    "forks": item.get("forks_count", 0),
                    "language": item.get("language") or "Unknown",
                    "license": license_info.get("spdx_id") or "Not specified",
                    "updated_at": (item.get("updated_at") or "")[:10],
                    "archived": item.get("archived", False),
                    "topics": item.get("topics", [])[:5],
                })
    except Exception:
        pass
    finally:
        if should_close:
            await client.aclose()

    return results


async def search_web(
    query: str,
    limit: int = 5,
    client: Optional[httpx.AsyncClient] = None
) -> List[Dict[str, Any]]:
    """Search DuckDuckGo Lite for relevant articles, tools, and documentation.

    Args:
        query: Search keywords
        limit: Max results to return
        client: Optional shared httpx client

    Returns:
        List of web result dicts with title, url, snippet.
    """
    if not query.strip():
        return []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote_plus(query)}"

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=6.0, follow_redirects=True)
        should_close = True

    results = []
    try:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            # Parse table rows containing result links
            link_matches = re.findall(
                r"<a[^>]+class=[\x27\"]result-link[\x27\"][^>]+href=[\x27\"]([^\x27\"]+)[\x27\"][^>]*>(.*?)</a>",
                resp.text,
                re.DOTALL
            )
            for link, raw_title in link_matches[:limit]:
                clean_url = link
                if "uddg=" in link:
                    clean_url = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                elif link.startswith("//"):
                    clean_url = "https:" + link

                clean_title = re.sub(r"<[^>]+>", "", raw_title).strip()
                if clean_url and clean_title:
                    results.append({
                        "source": "web",
                        "title": clean_title,
                        "url": clean_url,
                        "description": clean_title,
                    })
    except Exception:
        pass
    finally:
        if should_close:
            await client.aclose()

    return results


def search_local_skills(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Scan local installed skills directory for matching tools or workflows.

    Args:
        query: Search keywords
        limit: Max skills to return

    Returns:
        List of local skill metadata dicts.
    """
    if not os.path.isdir(SKILLS_DIR):
        return []

    query_tokens = [t.lower() for t in query.split() if len(t) > 2]
    matched = []

    try:
        for entry in sorted(os.listdir(SKILLS_DIR)):
            skill_path = os.path.join(SKILLS_DIR, entry)
            if not os.path.isdir(skill_path) or entry.startswith("."):
                continue

            skill_md = os.path.join(skill_path, "SKILL.md")
            description = ""
            if os.path.isfile(skill_md):
                try:
                    with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(1500)
                        # Extract description from frontmatter or first paragraph
                        desc_match = re.search(r"description:\s*([^\n]+)", content, re.IGNORECASE)
                        if desc_match:
                            description = desc_match.group(1).strip()
                        else:
                            lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith(("#", "---"))]
                            if lines:
                                description = lines[0][:150]
                except Exception:
                    pass

            score = 0
            entry_lower = entry.lower()
            desc_lower = description.lower()
            for token in query_tokens:
                if token in entry_lower:
                    score += 3
                elif token in desc_lower:
                    score += 1

            if score > 0 or not query_tokens:
                matched.append({
                    "score": score,
                    "source": "local-skill",
                    "title": f"Local Skill: {entry}",
                    "url": f"local://skills/{entry}",
                    "description": description or f"Domain skill installed at {skill_path}",
                    "skill_name": entry,
                })

        # Sort by score descending
        matched.sort(key=lambda x: x["score"], reverse=True)
    except Exception:
        pass

    return [{k: v for k, v in item.items() if k != "score"} for item in matched[:limit]]


def format_candidate_dossier(
    candidates: List[Dict[str, Any]],
    query: str,
    max_candidates: int = 6
) -> str:
    """Format discovered candidates into a high-density, structured Markdown dossier.

    Args:
        candidates: List of candidate dictionaries
        query: Original user query or search terms
        max_candidates: Maximum candidates to include in the output

    Returns:
        Structured Markdown text block for injection into deliberation prompt.
    """
    if not candidates:
        return ""

    lines = [
        f"=== DISCOVERED RESEARCH CANDIDATES FOR: \"{query}\" ===",
        f"The research engine scouted {len(candidates)} real-world candidates for evaluation.",
        "Council seats MUST evaluate these concrete candidates on quality, security, and fit:\n",
    ]

    for i, c in enumerate(candidates[:max_candidates], 1):
        source = c.get("source", "web").upper()
        title = c.get("title", "Untitled")
        url = c.get("url", "")
        desc = c.get("description", "").strip()

        # Format header with metrics if GitHub repository
        if source == "GITHUB":
            stars = c.get("stars", 0)
            forks = c.get("forks", 0)
            license_spdx = c.get("license", "Unknown")
            updated = c.get("updated_at", "")
            archived = c.get("archived", False)

            lines.append(f"### Candidate {i} [{source}]: {title}")
            lines.append(f"- **URL:** {url}")
            metric_line = f"- **Telemetry:** ⭐ {stars} stars | 🍴 {forks} forks | License: {license_spdx} | Updated: {updated}"
            if archived:
                metric_line += " | ⚠️ **ARCHIVED**"
            lines.append(metric_line)
            if c.get("topics"):
                lines.append(f"- **Topics:** {', '.join(c['topics'])}")
            lines.append(f"- **Overview:** {desc}\n")

        elif source == "LOCAL-SKILL":
            lines.append(f"### Candidate {i} [INSTALLED SKILL]: {title}")
            lines.append(f"- **Skill Identifier:** `{c.get('skill_name')}`")
            lines.append(f"- **Overview:** {desc}\n")

        else:
            lines.append(f"### Candidate {i} [WEB RESOURCE]: {title}")
            lines.append(f"- **URL:** {url}")
            lines.append(f"- **Summary:** {desc}\n")

    return "\n".join(lines)


async def run_research(
    query: str,
    max_candidates: int = 6,
    include_github: bool = True,
    include_web: bool = True,
    include_local_skills: bool = True
) -> Dict[str, Any]:
    """Execute a parallel multi-channel research inquiry and return structured dossier.

    Args:
        query: User question or search keywords
        max_candidates: Maximum items in final synthesized dossier
        include_github: Search GitHub repositories
        include_web: Search DuckDuckGo Lite
        include_local_skills: Scan local installed skills

    Returns:
        Dictionary with 'query', 'candidate_count', 'candidates', and 'dossier'.
    """
    search_terms = extract_search_terms(query)
    tasks = []

    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        if include_github:
            tasks.append(search_github_repositories(search_terms, limit=max_candidates, client=client))
        if include_web:
            tasks.append(search_web(search_terms, limit=max_candidates, client=client))

        # Run remote searches concurrently
        remote_results = await asyncio.gather(*tasks, return_exceptions=True)

    candidates = []
    # Local skills search (synchronous disk scan)
    if include_local_skills:
        try:
            local_skills = search_local_skills(search_terms, limit=3)
            candidates.extend(local_skills)
        except Exception:
            pass

    # Collect remote results
    for res in remote_results:
        if isinstance(res, list):
            candidates.extend(res)

    # Deduplicate candidates by URL
    seen_urls = set()
    deduped = []
    for c in candidates:
        url = c.get("url", "").lower()
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(c)
        elif not url:
            deduped.append(c)

    dossier = format_candidate_dossier(deduped, query, max_candidates=max_candidates)

    return {
        "query": query,
        "search_terms": search_terms,
        "candidate_count": len(deduped),
        "candidates": deduped[:max_candidates],
        "dossier": dossier,
    }


async def resolve_research_context(
    prompt: str,
    force: bool = False
) -> Tuple[str, Dict[str, Any]]:
    """Analyze prompt, conduct research if indicated, and enrich query with candidates.

    Args:
        prompt: Raw user query
        force: Force research even if heuristic doesn't trigger

    Returns:
        Tuple of (effective_query, research_metadata)
    """
    should_research = force or is_research_query(prompt)
    if not should_research:
        return prompt, {"researched": False}

    research_result = await run_research(prompt)
    dossier = research_result.get("dossier", "")
    if not dossier:
        return prompt, {"researched": False, "reason": "No candidates discovered"}

    enriched_query = f"{dossier}\n\n=== USER RESEARCH OBJECTIVE ===\n{prompt}"
    meta = {
        "researched": True,
        "search_terms": research_result.get("search_terms"),
        "candidate_count": research_result.get("candidate_count"),
        "candidates": research_result.get("candidates"),
    }
    return enriched_query, meta
