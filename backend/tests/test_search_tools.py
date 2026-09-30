"""Search tools: SearXNG, paper search, Wikipedia, and their registration."""

import asyncio

import httpx
import pytest

from backend.tools import search
from backend.tools.mcp_bridge import execute_tool, get_tool_definitions
from backend.tools.registry import get_tools_for_model

ARXIV_XML = """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>http://arxiv.org/abs/1706.03762</id><title>Attention Is
 All You Need</title><summary>We propose the Transformer.</summary>
<published>2017-06-12T00:00:00Z</published><author><name>A. Vaswani</name></author>
</entry></feed>"""


def _route(handler):
    """Make every httpx.AsyncClient created in search.py use a mock transport."""
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    return factory


@pytest.fixture
def mock_http(monkeypatch):
    def install(handler):
        monkeypatch.setattr(search.httpx, "AsyncClient", _route(handler))

    return install


def test_searxng_unconfigured_returns_none(monkeypatch):
    monkeypatch.setattr(search, "SEARXNG_URL", "")
    assert asyncio.run(search.searxng_search("x")) is None


def test_searxng_parses_and_clamps(monkeypatch, mock_http):
    monkeypatch.setattr(search, "SEARXNG_URL", "http://searxng:8080")
    seen = {}

    def handler(req):
        seen["params"] = dict(req.url.params)
        hits = [{"title": f"T{i}", "url": f"https://e.com/{i}", "content": "c" * 500} for i in range(20)]
        hits.append({"title": "no url"})
        return httpx.Response(200, json={"results": hits})

    mock_http(handler)
    res = asyncio.run(search.searxng_search("llm", limit=99))
    assert res is not None
    assert seen["params"]["format"] == "json"
    assert len(res) == 8  # clamped
    assert len(res[0]["description"]) == 300


def test_searxng_down_returns_none(monkeypatch, mock_http):
    monkeypatch.setattr(search, "SEARXNG_URL", "http://searxng:8080")

    def handler(_req):
        raise httpx.ConnectError("refused")

    mock_http(handler)
    assert asyncio.run(search.searxng_search("x")) is None


def test_paper_search_merges_sources_and_survives_one_failure(mock_http):
    def handler(req):
        if "arxiv" in req.url.host:
            return httpx.Response(200, text=ARXIV_XML)
        return httpx.Response(500)

    mock_http(handler)
    out = asyncio.run(search.tool_paper_search("transformer"))
    assert "Attention Is All You Need" in out
    assert "1706.03762" in out and "2017" in out
    assert "openalex" in out  # reported as unavailable, not a crash


def test_openalex_rebuilds_abstract(mock_http):
    payload = {"results": [{
        "id": "https://openalex.org/W1", "title": "Paper", "publication_year": 2020,
        "cited_by_count": 7, "authorships": [{"author": {"display_name": "Ada"}}],
        "abstract_inverted_index": {"hello": [0], "world": [1]},
    }]}
    mock_http(lambda _req: httpx.Response(200, json=payload))
    out = asyncio.run(search.tool_paper_search("x", source="openalex"))
    assert "hello world" in out and "7 citations" in out


def test_wikipedia_orders_by_relevance_and_sanitizes_lang(mock_http):
    seen = {}

    def handler(req):
        seen["host"] = req.url.host
        return httpx.Response(200, json={"query": {"pages": {
            "2": {"title": "Second", "index": 2, "extract": "b"},
            "1": {"title": "First Page", "index": 1, "extract": "a"},
        }}})

    mock_http(handler)
    out = asyncio.run(search.tool_wikipedia("x", lang="evil.com/"))
    assert seen["host"] == "en.wikipedia.org"  # bad lang code falls back
    assert out.index("First Page") < out.index("Second")
    assert "wiki/First_Page" in out


def test_empty_queries_rejected():
    assert asyncio.run(search.tool_paper_search("  ")).startswith("Error")
    assert asyncio.run(search.tool_wikipedia("")).startswith("Error")


def test_tools_registered_and_dispatched(monkeypatch):
    names = {d["function"]["name"] for d in get_tool_definitions(["paper_search", "wikipedia"])}
    assert names == {"paper_search", "wikipedia"}
    rt = {d["function"]["name"] for d in get_tools_for_model("m", is_roundtable=True)}
    assert {"paper_search", "wikipedia", "web_search"} <= rt

    async def fake(query, **kw):
        return f"ok:{query}:{kw['source']}"

    monkeypatch.setattr("backend.tools.mcp_bridge.tool_paper_search", fake)
    assert asyncio.run(execute_tool("paper_search", {"query": "q"})) == "ok:q:all"
