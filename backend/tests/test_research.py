import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from backend.research import (
    is_research_query,
    extract_search_terms,
    format_candidate_dossier,
    search_local_skills,
    search_github_repositories,
    search_web,
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
