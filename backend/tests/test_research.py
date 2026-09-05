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

