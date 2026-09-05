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
        "with", "best", "top", "find", "recommend", "show", "me", "tell", "give",
        "compare", "comparison", "evaluate", "evaluation", "versus"
    }
    words = [w for w in cleaned.split() if len(w) > 2 and w.lower() not in stop_words]
    return " ".join(words[:5]) if words else prompt[:40]


def extract_candidate_names(prompt: str) -> List[str]:
    """Extract named tools, libraries, or packages from queries like 'SQLite-vec vs Chroma' or '(A, B, C)'."""
    names: List[str] = []
    ignore_words = {
        "zero-dependency", "open-source", "real-time", "end-to-end",
        "built-in", "third-party", "high-level", "low-level",
        "in-memory", "server-side", "client-side", "e-commerce",
        "e.g", "eg", "ie", "vs", "or", "and", "the", "for", "with",
        "compare", "which", "what", "how", "best", "simple", "local",
        "python", "docker", "javascript", "typescript", "rust", "golang",
        "evaluate", "evaluation", "investigate", "analyze", "benchmark",
        "solutions", "applications", "database", "databases", "vector"
    }

    # 1. Look inside parentheses: e.g. (SQLite-vec, LanceDB, DuckDB-vss, Chroma)
    paren_match = re.search(r"\(([^)]+)\)", prompt)
    if paren_match:
        for part in re.split(r"[,/|;]", paren_match.group(1)):
            clean = re.sub(r"[^\w\-\.]", "", part).strip()
            if clean and len(clean) >= 2 and clean.lower() not in ignore_words:
                if clean not in names:
                    names.append(clean)

    # 2. Look for patterns like 'X vs Y' or 'X vs. Y'
    vs_matches = re.findall(r"\b([A-Za-z0-9_\-\.]+)\s+vs\.?\s+([A-Za-z0-9_\-\.]+)\b", prompt, re.I)
    for m in vs_matches:
        for item in m:
            clean = item.strip().strip(".")
            if clean and len(clean) >= 2 and clean.lower() not in ignore_words:
                if clean not in names:
                    names.append(clean)

    # 3. Look for phrases like 'alternatives to X or Y' / 'between X and Y'
    phrase_matches = re.findall(r"\b(?:to|like|between|than)\s+([A-Za-z0-9_\-\.]+)\s+(?:or|and)\s+([A-Za-z0-9_\-\.]+)\b", prompt, re.I)
    for m in phrase_matches:
        for item in m:
            clean = item.strip().strip(".")
            if clean and len(clean) >= 2 and clean.lower() not in ignore_words:
                if clean not in names:
                    names.append(clean)

    # 4. Look for hyphenated or compound library names (e.g. sqlite-vec, duckdb-vss)
    hyphenated = re.findall(r"\b([A-Za-z0-9]+[\-_][A-Za-z0-9\-_]+)\b", prompt)
    for h in hyphenated:
        clean = h.strip()
        if clean.lower() not in ignore_words and clean not in names and len(clean) >= 3:
            names.append(clean)

    # 5. Look for comma / 'and' separated tech tokens or tech-like words
    comma_parts = re.split(r",|\band\b", prompt, flags=re.IGNORECASE)
    if len(comma_parts) > 1:
        for part in comma_parts:
            words = [w.strip(" .?!;:") for w in part.split() if w.strip(" .?!;:")]
            for w in words:
                clean = re.sub(r"[^\w\-\.]", "", w).strip()
                if (
                    clean
                    and len(clean) >= 3
                    and clean.lower() not in ignore_words
                    and clean not in names
                    and (
                        "-" in clean
                        or "_" in clean
                        or clean.lower().endswith(("db", "vec", "vss", "lite", "sql", "ai", "store"))
                        or (clean[0].isupper() and any(c.islower() for c in clean[1:]))
                    )
                ):
                    names.append(clean)

    return names[:6]


async def _fetch_gh_repo_query(
    q: str,
    client: httpx.AsyncClient,
    headers: Dict[str, str],
    limit: int = 1
) -> List[Dict[str, Any]]:
    """Helper to query GitHub repository search API."""
    encoded_q = urllib.parse.quote(q.strip())
    url = f"{GITHUB_API_BASE}/search/repositories?q={encoded_q}&sort=stars&order=desc&per_page={limit}"
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
    return results


async def search_github_repositories(
    query: str,
    limit: int = 5,
    client: Optional[httpx.AsyncClient] = None
) -> List[Dict[str, Any]]:
    """Search public GitHub repositories for libraries, tools, or MCP servers.

    Args:
        query: Search keywords or prompt
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

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=8.0)
        should_close = True

    results = []
    seen_urls = set()

    try:
        extracted = extract_candidate_names(query)
        if extracted:
            # Combine candidates with OR to discover canonical repos in a single API call
            search_q = " OR ".join(extracted[:4])
            results = await _fetch_gh_repo_query(search_q, client, headers, limit=limit)
        else:
            terms = extract_search_terms(query).split()
            search_q = " ".join(terms[:3]) if terms else query[:30]
            results = await _fetch_gh_repo_query(search_q, client, headers, limit=limit)
    finally:
        if should_close:
            await client.aclose()

    return results[:limit]


async def search_web(
    query: str,
    limit: int = 5,
    client: Optional[httpx.AsyncClient] = None
) -> List[Dict[str, Any]]:
    """Search developer web resources, technical articles, and announcements.

    Args:
        query: Search keywords
        limit: Max results to return
        client: Optional shared httpx client

    Returns:
        List of web result dicts with title, url, snippet.
    """
    if not query.strip():
        return []

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=6.0, follow_redirects=True)
        should_close = True

    results = []
    # 1. High-signal developer articles & release announcements via Algolia HN API
    try:
        hn_url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote_plus(query)}&tags=story&hitsPerPage={limit}"
        resp = await client.get(hn_url)
        if resp.status_code == 200:
            hits = resp.json().get("hits", [])
            for h in hits:
                title = h.get("title")
                url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
                points = h.get("points") or 0
                num_comments = h.get("num_comments") or 0
                if title and url:
                    results.append({
                        "source": "web",
                        "title": title,
                        "url": url,
                        "description": f"Tech discussion & article ({points} points, {num_comments} comments)",
                    })
    except Exception:
        pass

    # 2. Web fallback (DuckDuckGo Lite) if needed
    if len(results) < limit:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            ddg_url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote_plus(query)}"
            resp = await client.get(ddg_url, headers=headers)
            if resp.status_code == 200:
                link_matches = re.findall(
                    r"<a[^>]+class=[\x27\"]result-link[\x27\"][^>]+href=[\x27\"]([^\x27\"]+)[\x27\"][^>]*>(.*?)</a>",
                    resp.text,
                    re.DOTALL
                )
                for link, raw_title in link_matches[:limit - len(results)]:
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

    if should_close:
        await client.aclose()

    return results[:limit]


async def search_pypi_package(
    package_name: str,
    client: Optional[httpx.AsyncClient] = None
) -> Optional[Dict[str, Any]]:
    """Look up a package directly on PyPI using canonical JSON API.

    Tries normalizations: lowercase, hyphens <-> underscores, and common suffixes (e.g. 'db').
    """
    if not package_name or len(package_name.strip()) < 2:
        return None

    norm = package_name.strip().lower()
    variations = [norm]
    if "-" in norm:
        variations.append(norm.replace("-", "_"))
    if "_" in norm:
        variations.append(norm.replace("_", "-"))
    if not norm.endswith("db") and not norm.endswith("-db"):
        variations.append(norm + "db")

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=4.0, follow_redirects=True)
        should_close = True

    try:
        for v in variations:
            try:
                url = f"https://pypi.org/pypi/{v}/json"
                headers = {"User-Agent": "LLM-Council-Research/1.0"}
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    info = data.get("info", {})
                    name = info.get("name") or v
                    summary = info.get("summary") or ""
                    # Guard against irrelevant packages (e.g. color manipulation 'chroma' instead of 'chromadb')
                    if v == "chroma" and "color" in summary.lower():
                        continue
                    license_str = (info.get("license") or info.get("license_expression") or "").strip()
                    if not license_str or license_str.lower() in ("unknown", "none"):
                        for c in info.get("classifiers", []):
                            if "License ::" in c:
                                license_str = c.split("::")[-1].strip()
                                break
                    if not license_str:
                        license_str = "Not specified"

                    target_url = info.get("package_url") or f"https://pypi.org/project/{name}/"
                    proj_urls = info.get("project_urls") or {}
                    github_repo_url = ""
                    for key in ["repository", "Source", "Source Code", "Homepage", "Code"]:
                        for k, val in proj_urls.items():
                            if k.lower() == key.lower() and "github.com" in str(val).lower():
                                github_repo_url = str(val).rstrip("/")
                                break
                        if github_repo_url:
                            break
                    if not github_repo_url:
                        for k, val in proj_urls.items():
                            if "github.com" in str(val).lower() and not any(sub in str(val).lower() for sub in ["/issues", "/pull", "/actions"]):
                                github_repo_url = str(val).rstrip("/")
                                break

                    return {
                        "source": "package",
                        "ecosystem": "pypi",
                        "title": name,
                        "url": target_url,
                        "github_url": github_repo_url,
                        "version": info.get("version", ""),
                        "license": license_str,
                        "description": summary or f"PyPI Python package '{name}'",
                    }
            except Exception:
                continue
    finally:
        if should_close:
            await client.aclose()

    return None


async def search_package_ecosystem(
    query: str,
    limit: int = 5,
    client: Optional[httpx.AsyncClient] = None
) -> List[Dict[str, Any]]:
    """Search open package registries (PyPI and NPM) for libraries, packages, and tools.

    Args:
        query: Search keywords or candidate prompt
        limit: Max results to return
        client: Optional shared httpx client

    Returns:
        List of package candidate dicts.
    """
    if not query.strip():
        return []

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=6.0, follow_redirects=True)
        should_close = True

    results = []
    seen_titles = set()

    try:
        candidates = extract_candidate_names(query)
        is_python_context = any(
            w in query.lower()
            for w in ["python", "pip", "py", "django", "fastapi", "flask", "pydantic", "torch", "numpy", "sqlite-vec"]
        )

        # 1. If explicit candidates or Python context detected, query PyPI first
        if candidates or is_python_context:
            target_pkgs = candidates if candidates else [t for t in extract_search_terms(query).split() if len(t) >= 3][:limit]
            pypi_tasks = [search_pypi_package(pkg, client=client) for pkg in target_pkgs]
            pypi_res = await asyncio.gather(*pypi_tasks, return_exceptions=True)
            for r in pypi_res:
                if isinstance(r, dict) and r.get("title") and r["title"].lower() not in seen_titles:
                    seen_titles.add(r["title"].lower())
                    results.append(r)

        # 2. If room remains and not exclusively Python candidates, query NPM registry
        if len(results) < limit and not (is_python_context and (candidates or results)):
            npm_query = " ".join(candidates[:2]) if candidates and not is_python_context else extract_search_terms(query)
            if npm_query:
                try:
                    url = f"https://registry.npmjs.org/-/v1/search?text={urllib.parse.quote_plus(npm_query)}&size={limit - len(results)}"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        for obj in resp.json().get("objects", []):
                            pkg = obj.get("package", {})
                            name = pkg.get("name")
                            if name and name.lower() not in seen_titles:
                                seen_titles.add(name.lower())
                                results.append({
                                    "source": "package",
                                    "ecosystem": "npm",
                                    "title": name,
                                    "url": pkg.get("links", {}).get("npm") or f"https://www.npmjs.com/package/{name}",
                                    "version": pkg.get("version", ""),
                                    "license": pkg.get("license", "Not specified") if isinstance(pkg.get("license"), str) else "Not specified",
                                    "description": pkg.get("description") or "Open source NPM package registry module.",
                                })
                except Exception:
                    pass
    finally:
        if should_close:
            await client.aclose()

    return results[:limit]


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

        elif source == "PACKAGE":
            ecosystem = c.get("ecosystem", "package").upper()
            version = c.get("version", "")
            license_val = c.get("license", "")
            github_url = c.get("github_url", "")
            lines.append(f"### Candidate {i} [{ecosystem} PACKAGE]: {title}")
            lines.append(f"- **URL:** {url}")
            if github_url:
                lines.append(f"- **Source Repo:** {github_url}")
            details = []
            if version:
                details.append(f"**Version:** {version}")
            if license_val:
                details.append(f"**License:** {license_val}")
            if details:
                lines.append(f"- {' | '.join(details)}")
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
    include_packages: bool = True,
    include_local_skills: bool = True
) -> Dict[str, Any]:
    """Execute a parallel multi-channel research inquiry and return structured dossier.

    Args:
        query: User question or search keywords
        max_candidates: Maximum items in final synthesized dossier
        include_github: Search GitHub repositories
        include_web: Search HackerNews Algolia & developer articles
        include_packages: Search open package ecosystems (PyPI & NPM)
        include_local_skills: Scan local installed skills

    Returns:
        Dictionary with 'query', 'candidate_count', 'candidates', and 'dossier'.
    """
    search_terms = extract_search_terms(query)
    tasks = []

    task_names = []
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        if include_github:
            tasks.append(search_github_repositories(query, limit=max_candidates, client=client))
            task_names.append("github")
        if include_web:
            tasks.append(search_web(search_terms, limit=max_candidates, client=client))
            task_names.append("web")
        if include_packages:
            tasks.append(search_package_ecosystem(query, limit=max_candidates, client=client))
            task_names.append("packages")

        # Run remote searches concurrently
        remote_results = await asyncio.gather(*tasks, return_exceptions=True)

    results_map: Dict[str, List[Dict[str, Any]]] = {
        "github": [],
        "web": [],
        "packages": [],
        "skills": [],
    }
    for name, res in zip(task_names, remote_results):
        if isinstance(res, list):
            results_map[name] = res

    # Local skills search (synchronous disk scan)
    if include_local_skills:
        try:
            local_skills = search_local_skills(search_terms, limit=3)
            results_map["skills"] = local_skills
        except Exception:
            pass

    # Order priority:
    # If the query asks for skills explicitly, prioritize skills first.
    # Otherwise, prioritize GitHub repositories and Package ecosystems, followed by skills and web.
    is_skill_query = any(w in query.lower() for w in ["skill", "skills", "yetenek"])
    if is_skill_query:
        ordered_sources = ["skills", "github", "packages", "web"]
    else:
        ordered_sources = ["github", "packages", "skills", "web"]

    candidates = []
    for s in ordered_sources:
        candidates.extend(results_map.get(s, []))

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
