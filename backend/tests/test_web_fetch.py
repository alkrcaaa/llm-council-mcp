"""web_fetch: markdown extraction, PDF, paging, cache, and the SSRF guard staying in charge."""

import asyncio
from types import SimpleNamespace

import pytest

from backend.netguard import BlockedURL
from backend.tools import builtin, mcp_bridge, webcontent

PAGE = """<html><head><title> Demo  Page </title><script>var x = 'SECRET_JS';</script></head>
<body><nav>Home | About</nav>
<header>Site banner</header>
<main><h1>Guide</h1><p>Intro with <a href="/docs/a">a link</a> and <strong>bold</strong> and <code>x()</code>.</p>
<ul><li>one</li><li>two<ul><li>nested</li></ul></li></ul>
<ol><li>first</li><li>second</li></ol>
<pre>line1
  line2</pre>
<table><tr><th>k</th><th>v</th></tr><tr><td>a</td><td>1</td></tr></table>
<a href="javascript:evil()">bad</a><img src="x.png" alt="pic">
%s
</main><footer>Copyright junk</footer></body></html>""" % ("<p>filler text. </p>" * 20)


def make_pdf(text: str) -> bytes:
    """Smallest valid one-page PDF containing `text`."""
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    return out


@pytest.fixture(autouse=True)
def clean_cache():
    webcontent.cache_clear()
    yield
    webcontent.cache_clear()


def fake_get(monkeypatch, body, ctype="text/html; charset=utf-8", status=200):
    calls = []

    async def safe_get(url, **kw):
        calls.append(url)
        resp = SimpleNamespace(status_code=status, headers={"content-type": ctype}, charset_encoding="utf-8")
        return resp, body

    monkeypatch.setattr(builtin, "safe_get", safe_get)
    return calls


def fetch(url="https://example.com/p", **kw):
    return asyncio.run(builtin.tool_web_fetch(url, **kw))


def test_html_becomes_clean_markdown():
    title, md = webcontent.html_to_markdown(PAGE, "https://example.com/p")
    assert title == "Demo Page"
    assert md.startswith("# Guide")
    assert "[a link](https://example.com/docs/a)" in md  # relative -> absolute
    assert "**bold**" in md and "`x()`" in md
    assert "- one" in md and "  - nested" in md and "1. first" in md and "2. second" in md
    assert "```\nline1\n  line2\n```" in md
    assert "| k | v |" in md and "| a | 1 |" in md
    for junk in ("SECRET_JS", "Home | About", "Site banner", "Copyright junk", "javascript:", "x.png"):
        assert junk not in md


def test_page_without_main_keeps_body_but_not_chrome():
    html = "<body><nav>menu</nav><div><p>" + "real content " * 30 + "</p></div><footer>f</footer></body>"
    _, md = webcontent.html_to_markdown(html, "https://e.com")
    assert "real content" in md and "menu" not in md


def test_pdf_text_extracted(monkeypatch):
    fake_get(monkeypatch, make_pdf("Hello PDF world"), ctype="application/pdf")
    out = fetch("https://example.com/a.pdf")
    assert "Hello PDF world" in out and "[page 1]" in out


def test_broken_and_oversized_pdf_reported(monkeypatch):
    fake_get(monkeypatch, b"%PDF-1.4 garbage", ctype="application/pdf")
    assert fetch("https://example.com/a.pdf").startswith("Error reading")
    fake_get(monkeypatch, b"x" * builtin.PDF_MAX_BYTES, ctype="application/pdf")
    assert "larger than" in fetch("https://example.com/b.pdf")


def test_paging_with_start_index(monkeypatch):
    fake_get(monkeypatch, ("word " * 4000).encode(), ctype="text/plain")
    first = fetch(max_chars=1000)
    assert "Characters 0-1000 of" in first and "start_index=1000" in first
    second = fetch(max_chars=1000, start_index=1000)
    assert "Characters 1000-2000 of" in second
    last = fetch(max_chars=20000, start_index=15000)
    assert "truncated" not in last
    assert "past the end" in fetch(start_index=10**6)


def test_cache_avoids_second_network_call(monkeypatch):
    calls = fake_get(monkeypatch, PAGE.encode())
    fetch()
    fetch(start_index=10)
    assert len(calls) == 1
    webcontent.cache_clear()
    fetch()
    assert len(calls) == 2


def test_cache_expires_and_is_bounded(monkeypatch):
    webcontent.cache_put("u", ("t", "body"))
    assert webcontent.cache_get("u") == ("t", "body")
    real = webcontent.time.monotonic
    monkeypatch.setattr(webcontent.time, "monotonic", lambda: real() + webcontent.CACHE_TTL_S + 1)
    assert webcontent.cache_get("u") is None
    monkeypatch.undo()
    for i in range(webcontent.CACHE_MAX_ENTRIES + 5):
        webcontent.cache_put(f"k{i}", ("", "x"))
    assert len(webcontent._cache) == webcontent.CACHE_MAX_ENTRIES
    webcontent.cache_put("huge", ("", "x" * (webcontent.CACHE_MAX_ENTRY_CHARS + 1)))
    assert webcontent.cache_get("huge") is None


def test_errors_are_reported_not_raised(monkeypatch):
    fake_get(monkeypatch, b"", status=404)
    assert "HTTP 404" in fetch()

    async def blocked(url, **kw):
        raise BlockedURL("host resolves to a non-public address: x")

    monkeypatch.setattr(builtin, "safe_get", blocked)
    assert fetch("http://169.254.169.254/").startswith("Error: URL blocked")
    assert fetch("not-a-number", max_chars="abc").startswith("Error: max_chars")


def test_execute_tool_never_uses_external_fetch_mcp(monkeypatch):
    """The fetch MCP server would bypass the SSRF guard, so web_fetch must not call it."""
    def forbidden(*a, **k):
        raise AssertionError("external MCP fetch must not be used")

    monkeypatch.setattr(mcp_bridge, "call_http_mcp_tool", forbidden)
    fake_get(monkeypatch, b"hello there", ctype="text/plain")
    out = asyncio.run(mcp_bridge.execute_tool("web_fetch", {"url": "https://example.com/x"}))
    assert "hello there" in out


def test_schema_exposes_start_index():
    props = mcp_bridge.BUILTIN_TOOL_SCHEMAS["web_fetch"]["function"]["parameters"]["properties"]
    assert "start_index" in props
