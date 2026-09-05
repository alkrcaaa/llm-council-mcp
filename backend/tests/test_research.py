import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from backend.research import (
    is_research_query,
    extract_search_terms,
    extract_candidate_names,
    format_candidate_dossier,
    search_local_skills,
    search_github_repositories,
    search_web,
    search_package_ecosystem,
    search_pypi_package,
    run_research,
    resolve_research_context,
    _fetch_gh_repo_query,
)


def test_is_research_query_heuristics():
    # Negative cases: normal coding, chat, math
    assert not is_research_query("")
    assert not is_research_query("hello")
    assert not is_research_query("2 + 2 kaç eder?")
    assert not is_research_query("Write a python function to parse json")
    assert not is_research_query("Fix the null pointer exception in auth.py")

    # Positive cases: English technology scouting
    assert is_research_query("Find best mcp servers for sqlite integration")
    assert is_research_query("Discover top tools and skills for vulnerability scanning")
    assert is_research_query("Research alternative mcps for browser automation")

    # Positive cases: Turkish research prompts
    assert is_research_query("Obsidian için en iyi mcp sunucularını araştır")
    assert is_research_query("Hangi skill ve tool alternatifleri var keşfet")
    assert is_research_query("Web scraping için mcpleri listele ve bul")


def test_extract_search_terms():
    terms = extract_search_terms("Obsidian için en iyi mcp sunucularını araştır lütfen")
    assert "obsidian" in terms.lower()
    assert "mcp" in terms.lower()
    # Stop words should be stripped
    assert "için" not in terms.lower()
    assert "lütfen" not in terms.lower()

    terms_en = extract_search_terms("What are the best tools for docker container scanning?")
    assert "tools" in terms_en.lower() or "docker" in terms_en.lower()
    assert "what" not in terms_en.lower()


def test_format_candidate_dossier():
    candidates = [
        {
            "title": "calclavia/mcp-obsidian",
            "url": "https://github.com/calclavia/mcp-obsidian",
            "stars": 340,
            "forks": 25,
            "license": "MIT",
            "description": "Model Context Protocol server for reading and writing to Obsidian vaults.",
            "source": "github",
        },
        {
            "title": "Local Skill: owasp-security",
            "url": "local://skills/owasp-security",
            "skill_name": "owasp-security",
            "description": "Security audit and vulnerability review skill.",
            "source": "local-skill",
        }
    ]

    dossier = format_candidate_dossier(candidates, "obsidian mcp")
    assert "DISCOVERED RESEARCH CANDIDATES FOR" in dossier
    assert "obsidian mcp" in dossier
    assert "calclavia/mcp-obsidian" in dossier
    assert "340 stars" in dossier
    assert "MIT" in dossier
    assert "owasp-security" in dossier
    assert "Low signal:" not in dossier


def test_search_local_skills():
    skills = search_local_skills("security", limit=5)
    # The ~/.gemini/config/skills directory has owasp-security
    if skills:
        assert any("security" in s["title"].lower() or "security" in s["description"].lower() for s in skills)
        assert skills[0]["source"] == "local-skill"


@pytest.mark.asyncio
async def test_search_github_repositories_mocked():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {
                "full_name": "example/mcp-server",
                "html_url": "https://github.com/example/mcp-server",
                "description": "A sample MCP server for testing.",
                "stargazers_count": 150,
                "forks_count": 12,
                "license": {"spdx_id": "Apache-2.0"},
                "topics": ["mcp", "ai", "tools"],
            }
        ]
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    results = await search_github_repositories("mcp server", limit=3, client=mock_client)
    assert len(results) == 1
    assert results[0]["title"] == "example/mcp-server"
    assert results[0]["stars"] == 150
    assert results[0]["license"] == "Apache-2.0"
    assert results[0]["source"] == "github"


@pytest.mark.asyncio
async def test_search_github_repositories_error_handling():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.RequestError("Connection timeout")

    results = await search_github_repositories("test", client=mock_client)
    assert results == []


@pytest.mark.asyncio
async def test_search_web_duckduckgo_lite_mocked():
    sample_html = """
    <html>
    <body>
    <table>
      <tr>
        <td>
          <a class="result-link" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fgithub.com%2Fmodelcontextprotocol%2Fservers&rut=1">MCP Official Servers</a>
        </td>
      </tr>
    </table>
    </body>
    </html>
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = sample_html

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    results = await search_web("mcp servers", limit=3, client=mock_client)
    assert len(results) == 1
    assert results[0]["title"] == "MCP Official Servers"
    assert results[0]["url"] == "https://github.com/modelcontextprotocol/servers"
    assert results[0]["source"] == "web"


@pytest.mark.asyncio
async def test_resolve_research_context():
    # Non-research prompt without force
    normal_prompt = "Write a binary search algorithm in Python"
    query, meta = await resolve_research_context(normal_prompt, force=False)
    assert query == normal_prompt
    assert meta["researched"] is False

    # Force research with mocked run_research
    mock_run = {
        "query": normal_prompt,
        "search_terms": "binary search",
        "candidate_count": 1,
        "candidates": [{"title": "test-repo", "url": "https://github.com/test/repo"}],
        "dossier": "=== DISCOVERED RESEARCH CANDIDATES FOR: test ===",
    }
    with patch("backend.research.run_research", AsyncMock(return_value=mock_run)):
        query, meta = await resolve_research_context(normal_prompt, force=True)
        assert meta["researched"] is True
        assert meta["candidate_count"] == 1
        assert "DISCOVERED RESEARCH CANDIDATES FOR" in query
        assert "=== USER RESEARCH OBJECTIVE ===" in query


@pytest.mark.asyncio
async def test_search_package_ecosystem_mocked():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "objects": [
            {
                "package": {
                    "name": "@modelcontextprotocol/server-filesystem",
                    "version": "0.6.2",
                    "description": "MCP server for filesystem access",
                    "links": {"npm": "https://www.npmjs.com/package/@modelcontextprotocol/server-filesystem"}
                }
            }
        ]
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    results = await search_package_ecosystem("filesystem mcp", limit=2, client=mock_client)
    assert len(results) == 1
    assert results[0]["title"] == "@modelcontextprotocol/server-filesystem"
    assert results[0]["source"] == "package"
    assert results[0]["version"] == "0.6.2"


@pytest.mark.asyncio
async def test_scout_endpoints():
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    mock_run = {
        "query": "vector db",
        "search_terms": "vector db",
        "candidate_count": 2,
        "candidates": [
            {"title": "qdrant/qdrant", "url": "https://github.com/qdrant/qdrant", "source": "github"}
        ],
        "dossier": "=== DISCOVERED RESEARCH CANDIDATES ===",
    }

    with patch("backend.research.run_research", AsyncMock(return_value=mock_run)):
        # Test POST /api/research/scout
        resp = client.post("/api/research/scout", json={"query": "vector db", "max_candidates": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "vector db"
        assert len(data["candidates"]) == 1

        # Test GET /api/research/scout
        resp_get = client.get("/api/research/scout?query=vector+db&max_candidates=3")
        assert resp_get.status_code == 200
        data_get = resp_get.json()
        assert data_get["query"] == "vector db"


def test_extract_candidate_names():
    # Parenthetical list
    res1 = extract_candidate_names("Evaluate (SQLite-vec, LanceDB, DuckDB-vss, Chroma)")
    assert "SQLite-vec" in res1
    assert "LanceDB" in res1
    assert "DuckDB-vss" in res1
    assert "Chroma" in res1

    # X vs Y pattern
    res2 = extract_candidate_names("Compare SQLite-vec vs Chroma for local vector store")
    assert "SQLite-vec" in res2
    assert "Chroma" in res2

    # Alternatives pattern
    res3 = extract_candidate_names("What are good alternatives to Qdrant or Milvus?")
    assert "Qdrant" in res3
    assert "Milvus" in res3


@pytest.mark.asyncio
async def test_search_pypi_package_mocked():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "info": {
            "name": "sqlite-vec",
            "version": "0.1.9",
            "summary": "A vector search extension for SQLite",
            "license": "Apache-2.0",
            "package_url": "https://pypi.org/project/sqlite-vec/",
            "project_urls": {"Homepage": "https://github.com/asg017/sqlite-vec"}
        }
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    res = await search_pypi_package("sqlite-vec", client=mock_client)
    assert res is not None
    assert res["title"] == "sqlite-vec"
    assert res["ecosystem"] == "pypi"
    assert res["version"] == "0.1.9"
    assert res["license"] == "Apache-2.0"
    assert "pypi.org/project/sqlite-vec" in res["url"]


@pytest.mark.asyncio
async def test_search_package_ecosystem_pypi_routing():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "info": {
            "name": "chromadb",
            "version": "1.5.9",
            "summary": "AI native vector database",
            "license": "Apache-2.0",
            "package_url": "https://pypi.org/project/chromadb/",
        }
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    results = await search_package_ecosystem("Evaluate Chroma for Python", limit=2, client=mock_client)
    assert len(results) >= 1
    assert any(r.get("ecosystem") == "pypi" for r in results)


def test_format_candidate_dossier_package():
    candidates = [
        {
            "title": "sqlite-vec",
            "url": "https://pypi.org/project/sqlite-vec/",
            "version": "0.1.9",
            "license": "Apache-2.0",
            "description": "Vector search extension for SQLite",
            "source": "package",
            "ecosystem": "pypi",
        }
    ]

    dossier = format_candidate_dossier(candidates, "sqlite-vec")
    assert "PYPI PACKAGE" in dossier
    assert "sqlite-vec" in dossier
    assert "0.1.9" in dossier
    assert "Apache-2.0" in dossier


@pytest.mark.asyncio
async def test_fetch_gh_repo_query_no_sort_stars_and_filters_archived():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    captured_url = None

    async def fake_get(url, headers=None):
        nonlocal captured_url
        captured_url = url
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "items": [
                {
                    "full_name": "relevant/active-repo",
                    "html_url": "https://github.com/relevant/active-repo",
                    "description": "Active relevant tool",
                    "stargazers_count": 50,
                    "forks_count": 5,
                    "archived": False,
                },
                {
                    "full_name": "abandoned/archived-repo",
                    "html_url": "https://github.com/abandoned/archived-repo",
                    "description": "Archived old tool",
                    "stargazers_count": 5000,
                    "forks_count": 200,
                    "archived": True,
                },
                {
                    "full_name": "relevant/second-repo",
                    "html_url": "https://github.com/relevant/second-repo",
                    "description": "Another relevant tool",
                    "stargazers_count": 25,
                    "forks_count": 2,
                    "archived": False,
                },
            ]
        }
        return resp

    mock_client.get = fake_get

    results = await _fetch_gh_repo_query("obsidian sync mcp server", mock_client, {}, limit=2)
    assert captured_url is not None
    assert "sort=stars" not in captured_url
    assert "order=desc" not in captured_url
    assert "per_page=6" in captured_url
    # Archived repo must be filtered out
    assert len(results) == 2
    assert results[0]["title"] == "relevant/active-repo"
    assert results[1]["title"] == "relevant/second-repo"
    # Verify GitHub's original relevance order is preserved (50 stars before 25 stars, NOT sorted by stars)
    assert results[0]["stars"] == 50
    assert results[1]["stars"] == 25


def test_extract_candidate_names_ignores_compound_adjectives():
    # 'local-first', 'privacy-first', 'cloud-native' should NOT be extracted as candidates
    extracted = extract_candidate_names("Find local-first obsidian sync mcp server with privacy-first storage")
    assert "local-first" not in extracted
    assert "privacy-first" not in extracted
    assert extracted == []


@pytest.mark.asyncio
async def test_search_github_repositories_preserves_multi_term_query():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    captured_url = None

    async def fake_get(url, headers=None):
        nonlocal captured_url
        captured_url = url
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"items": []}
        return resp

    mock_client.get = fake_get

    await search_github_repositories("local-first obsidian sync mcp server", limit=4, client=mock_client)
    assert captured_url is not None
    import urllib.parse
    parsed_q = urllib.parse.unquote(captured_url)
    assert "obsidian" in parsed_q
    assert "sync" in parsed_q
    assert "mcp" in parsed_q
    assert "server" in parsed_q
    assert "sort=stars" not in parsed_q


@pytest.mark.asyncio
async def test_scout_niche_query_relevance():
    # Acceptance criteria from SCOUT_RELEVANCE_FIX.md
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {
                "full_name": "jimprosser/obsidian-web-mcp",
                "html_url": "https://github.com/jimprosser/obsidian-web-mcp",
                "description": "Secure remote MCP server for Obsidian vaults",
                "stargazers_count": 167,
                "forks_count": 10,
                "archived": False,
            },
            {
                "full_name": "es617/obsidian-sync-mcp",
                "html_url": "https://github.com/es617/obsidian-sync-mcp",
                "description": "MCP server for Obsidian — access your vault from any AI agent",
                "stargazers_count": 50,
                "forks_count": 4,
                "archived": False,
            },
        ]
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    results = await search_github_repositories("local-first obsidian sync mcp server", limit=4, client=mock_client)
    titles = [c["title"].lower() for c in results]
    assert len(titles) == 2
    # Generic mega-repos must NOT crowd out relevant hits
    assert not any(t in {"home-assistant/core", "mintplex-labs/anything-llm", "nexu-io/open-design"} for t in titles)
    # Must be topically relevant
    assert all("obsidian" in t or "mcp" in t or "sync" in t for t in titles)


def test_format_candidate_dossier_maturity_signal():
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    recent_date = (now - timedelta(days=10)).strftime("%Y-%m-%d")
    old_date = (now - timedelta(days=120)).strftime("%Y-%m-%d")

    candidates = [
        {
            "title": "new-author/toy-mcp",
            "url": "https://github.com/new-author/toy-mcp",
            "stars": 0,
            "forks": 0,
            "license": "MIT",
            "updated_at": recent_date,
            "description": "Brand new MCP server created last week.",
            "source": "github",
        },
        {
            "title": "growing/new-tool",
            "url": "https://github.com/growing/new-tool",
            "stars": 5,
            "forks": 1,
            "license": "Apache-2.0",
            "updated_at": recent_date,
            "description": "Small repo with 5 stars.",
            "source": "github",
        },
        {
            "title": "moderate/tool-repo",
            "url": "https://github.com/moderate/tool-repo",
            "stars": 45,
            "forks": 5,
            "license": "MIT",
            "updated_at": recent_date,
            "description": "Moderate repo with 45 stars.",
            "source": "github",
        },
        {
            "title": "old/abandoned-repo",
            "url": "https://github.com/old/abandoned-repo",
            "stars": 2,
            "forks": 0,
            "license": "MIT",
            "updated_at": old_date,
            "description": "Old repo with 2 stars updated 120 days ago.",
            "source": "github",
        },
    ]

    dossier = format_candidate_dossier(candidates, "mcp tool")

    # Candidate 1 (0 stars, recent) -> MUST have warning
    assert "- ⚠️ **Low signal:** new/unstarred repo (0★, created/updated recently) — verify independently before relying on it." in dossier

    # Candidate 2 (5 stars, recent) -> MUST have warning
    assert "- ⚠️ **Low signal:** new/unstarred repo (5★, created/updated recently) — verify independently before relying on it." in dossier

    # Candidate 3 (45 stars, recent) -> in between, NO warning
    assert "new/unstarred repo (45★" not in dossier

    # Candidate 4 (2 stars, 120 days old) -> > 90 days, NO recent warning
    assert "new/unstarred repo (2★" not in dossier



