"""Search tools: SearXNG web search, paper search (arXiv, OpenAlex) and Wikipedia.

SearXNG is our own self-hosted instance on the compose-internal network (SEARXNG_URL), so
these calls go through plain httpx rather than netguard's public-URL-only fetcher. When
SEARXNG_URL is unset or the instance is down, callers fall back to the legacy HN/DDG search.
"""

import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import httpx

SEARXNG_URL = os.getenv("SEARXNG_URL", "").rstrip("/")
_TIMEOUT = 10.0
_UA = {"User-Agent": "llm-council/1.0 (research tool)"}
_ATOM = {"a": "http://www.w3.org/2005/Atom"}


def _clamp(limit: Any, default: int = 5, hi: int = 8) -> int:
    try:
        return max(1, min(hi, int(limit)))
    except (TypeError, ValueError):
        return default


async def searxng_search(query: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
    """Query SearXNG. Returns None when unconfigured or unreachable so callers can fall back."""
    if not SEARXNG_URL or not query.strip():
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_UA) as client:
            resp = await client.get(
                f"{SEARXNG_URL}/search",
                params={"q": query, "format": "json", "safesearch": 0},
            )
        if resp.status_code != 200:
            return None
        hits = resp.json().get("results", [])
    except Exception:
        return None
    return [
        {
            "title": h.get("title") or "Untitled",
            "url": h.get("url", ""),
            "description": (h.get("content") or "")[:300],
        }
        for h in hits[: _clamp(limit)]
        if h.get("url")
    ]


async def _arxiv(client: httpx.AsyncClient, query: str, limit: int) -> List[Dict[str, Any]]:
    resp = await client.get(
        "https://export.arxiv.org/api/query",
        params={"search_query": f"all:{query}", "max_results": limit, "sortBy": "relevance"},
    )
    resp.raise_for_status()
    out = []
    for entry in ET.fromstring(resp.text).findall("a:entry", _ATOM):
        def text(tag: str) -> str:
            return (entry.findtext(f"a:{tag}", default="", namespaces=_ATOM) or "").strip()

        authors = [
            (a.findtext("a:name", default="", namespaces=_ATOM) or "").strip()
            for a in entry.findall("a:author", _ATOM)
        ]
        out.append({
            "source": "arXiv",
            "title": " ".join(text("title").split()),
            "url": text("id"),
            "authors": authors[:4],
            "year": text("published")[:4],
            "abstract": " ".join(text("summary").split())[:500],
        })
    return out


def _openalex_abstract(inv: Optional[Dict[str, List[int]]]) -> str:
    """OpenAlex ships abstracts as {word: [positions]}; rebuild the text."""
    if not inv:
        return ""
    words: Dict[int, str] = {}
    for word, positions in inv.items():
        for p in positions:
            words[p] = word
    return " ".join(words[i] for i in sorted(words))[:500]


async def _openalex(client: httpx.AsyncClient, query: str, limit: int) -> List[Dict[str, Any]]:
    resp = await client.get(
        "https://api.openalex.org/works",
        params={"search": query, "per-page": limit, "select": "id,title,doi,publication_year,"
                "authorships,cited_by_count,abstract_inverted_index"},
    )
    resp.raise_for_status()
    out = []
    for w in resp.json().get("results", []):
        out.append({
            "source": "OpenAlex",
            "title": w.get("title") or "Untitled",
            "url": w.get("doi") or w.get("id", ""),
            "authors": [a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])[:4]],
            "year": str(w.get("publication_year") or ""),
            "citations": w.get("cited_by_count", 0),
            "abstract": _openalex_abstract(w.get("abstract_inverted_index")),
        })
    return out


async def tool_paper_search(query: str, limit: int = 5, source: str = "all") -> str:
    """Search academic papers on arXiv and OpenAlex.

    Args:
        query: Topic or title keywords
        limit: Results per source (1-8, default 5)
        source: 'arxiv', 'openalex' or 'all'
    """
    if not query.strip():
        return "Error: empty paper search query."
    limit = _clamp(limit)
    fetchers = {"arxiv": _arxiv, "openalex": _openalex}
    chosen = [source] if source in fetchers else list(fetchers)

    papers: List[Dict[str, Any]] = []
    errors: List[str] = []
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_UA, follow_redirects=True) as client:
        for name in chosen:
            try:
                papers.extend(await fetchers[name](client, query, limit))
            except Exception as e:
                errors.append(f"{name}: {type(e).__name__}")

    if not papers:
        detail = f" ({', '.join(errors)})" if errors else ""
        return f"No papers found for '{query}'{detail}."

    lines = [f"### Paper search results for: {query}\n"]
    for i, p in enumerate(papers, 1):
        meta = ", ".join(x for x in (", ".join(p["authors"]), p["year"], p["source"]) if x)
        cites = f" · {p['citations']} citations" if p.get("citations") else ""
        lines.append(f"{i}. **[{p['title']}]({p['url']})**\n   {meta}{cites}\n   {p['abstract']}\n")
    if errors:
        lines.append(f"(unavailable: {', '.join(errors)})")
    return "\n".join(lines)


async def tool_wikipedia(query: str, lang: str = "en", limit: int = 3) -> str:
    """Look up Wikipedia articles and return their introductions.

    Args:
        query: Topic or article title
        lang: Wikipedia language code (default 'en')
        limit: Max articles (1-5, default 3)
    """
    if not query.strip():
        return "Error: empty Wikipedia query."
    lang = lang if lang.isalpha() and len(lang) <= 3 else "en"
    limit = _clamp(limit, default=3, hi=5)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_UA) as client:
            resp = await client.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={
                    "action": "query", "format": "json", "generator": "search",
                    "gsrsearch": query, "gsrlimit": limit, "prop": "extracts",
                    "exintro": 1, "explaintext": 1, "exlimit": limit, "redirects": 1,
                },
            )
        resp.raise_for_status()
        pages = sorted(
            resp.json().get("query", {}).get("pages", {}).values(),
            key=lambda p: p.get("index", 99),
        )
    except Exception as e:
        return f"Error querying Wikipedia: {type(e).__name__}"

    if not pages:
        return f"No Wikipedia article found for '{query}'."
    out = [f"### Wikipedia ({lang}) results for: {query}\n"]
    for p in pages:
        title = p.get("title", "Untitled")
        url = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
        out.append(f"**[{title}]({url})**\n{(p.get('extract') or '').strip()[:1200]}\n")
    return "\n".join(out)
