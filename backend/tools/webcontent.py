"""Turn fetched pages into clean markdown for models: HTML, PDF and plain text, with a cache.

HTML is converted with the stdlib parser (no extra dependency); when the page has a <main>
or <article> element only that is kept, otherwise everything except obvious chrome
(nav/footer/aside/forms/scripts).
"""

import asyncio
import io
import re
import time
from collections import OrderedDict
from html.parser import HTMLParser
from typing import List, Optional, Tuple
from urllib.parse import urljoin

SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "aside", "form", "svg",
             "iframe", "template", "head", "button", "select", "dialog"}
BLOCK_TAGS = {"p", "div", "section", "article", "main", "header", "ul", "ol", "table",
              "figure", "figcaption", "details", "summary", "dl", "dt", "dd"}
VOID_SKIP = {"br", "hr", "img", "input", "meta", "link"}
MAX_PDF_PAGES = 40
CACHE_TTL_S = 900.0
CACHE_MAX_ENTRIES = 64
CACHE_MAX_ENTRY_CHARS = 500_000


class _Markdown(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self.all: List[str] = []
        self.main: List[str] = []
        self._skip = 0
        self._main_depth = 0
        self._in_title = False
        self._pre = 0
        self._lists: List[str] = []  # 'ul' | 'ol:<n>'
        self._links: List[Optional[str]] = []

    def _w(self, text: str) -> None:
        self.all.append(text)
        if self._main_depth:
            self.main.append(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
            return
        if tag in SKIP_TAGS:
            if tag not in VOID_SKIP:
                self._skip += 1
            return
        if self._skip:
            return
        if tag in ("main", "article"):
            self._main_depth += 1
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._w("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "br":
            self._w("\n")
        elif tag == "hr":
            self._w("\n\n---\n\n")
        elif tag == "pre":
            self._pre += 1
            self._w("\n\n```\n")
        elif tag == "code" and not self._pre:
            self._w("`")
        elif tag in ("strong", "b"):
            self._w("**")
        elif tag in ("em", "i"):
            self._w("*")
        elif tag == "blockquote":
            self._w("\n\n> ")
        elif tag in ("ul", "ol"):
            self._lists.append("ul" if tag == "ul" else "ol:0")
            self._w("\n")
        elif tag == "li":
            indent = "  " * max(0, len(self._lists) - 1)
            if self._lists and self._lists[-1].startswith("ol"):
                n = int(self._lists[-1].split(":")[1]) + 1
                self._lists[-1] = f"ol:{n}"
                self._w(f"\n{indent}{n}. ")
            else:
                self._w(f"\n{indent}- ")
        elif tag == "tr":
            self._w("\n| ")
        elif tag in ("td", "th"):
            pass
        elif tag == "a":
            href = (a.get("href") or "").strip()
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                self._links.append(urljoin(self.base_url, href))
                self._w("[")
            else:
                self._links.append(None)
        elif tag in BLOCK_TAGS:
            self._w("\n\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
            return
        if tag in SKIP_TAGS:
            if tag not in VOID_SKIP and self._skip:
                self._skip -= 1
            return
        if self._skip:
            return
        if tag in ("main", "article") and self._main_depth:
            self._main_depth -= 1
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._w("\n\n")
        elif tag == "pre" and self._pre:
            self._pre -= 1
            self._w("\n```\n\n")
        elif tag == "code" and not self._pre:
            self._w("`")
        elif tag in ("strong", "b"):
            self._w("**")
        elif tag in ("em", "i"):
            self._w("*")
        elif tag in ("ul", "ol"):
            if self._lists:
                self._lists.pop()
            self._w("\n")
        elif tag in ("td", "th"):
            self._w(" | ")
        elif tag == "a" and self._links:
            href = self._links.pop()
            if href:
                self._w(f"]({href})")
        elif tag in BLOCK_TAGS or tag == "blockquote":
            self._w("\n\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if self._skip:
            return
        self._w(data if self._pre else re.sub(r"\s+", " ", data))


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+(?=\n)", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?m)^\| ?(?:\| ?)*$", "", text)  # empty table rows
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def html_to_markdown(html_text: str, base_url: str = "") -> Tuple[str, str]:
    """Return (title, markdown). Prefers <main>/<article> content when present."""
    parser = _Markdown(base_url)
    parser.feed(html_text)
    parser.close()
    main = _tidy("".join(parser.main))
    body = main if len(main) > 200 else _tidy("".join(parser.all))
    return " ".join(parser.title.split()), body


def pdf_to_text(data: bytes) -> str:
    """Extract text from a PDF (first MAX_PDF_PAGES pages). Raises ValueError on unusable input."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("PDF is encrypted")
        pages = []
        for i, page in enumerate(reader.pages[:MAX_PDF_PAGES], 1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(f"[page {i}]\n{text}")
        total = len(reader.pages)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"could not read PDF ({type(e).__name__})") from e
    if not pages:
        raise ValueError("PDF has no extractable text (scanned image?)")
    out = "\n\n".join(pages)
    if total > MAX_PDF_PAGES:
        out += f"\n\n[... only the first {MAX_PDF_PAGES} of {total} pages were read ...]"
    return out


async def extract(body: bytes, content_type: str, charset: Optional[str], url: str) -> Tuple[str, str]:
    """Return (title, markdown/plain text) for a fetched body."""
    ctype = content_type.split(";")[0].strip().lower()
    if ctype == "application/pdf":
        return "", await asyncio.to_thread(pdf_to_text, body)
    text = body.decode(charset or "utf-8", errors="replace")
    if "html" in ctype:
        return await asyncio.to_thread(html_to_markdown, text, url)
    return "", text.strip()


# --- cache -------------------------------------------------------------------------------

_cache: "OrderedDict[str, Tuple[float, Tuple[str, str]]]" = OrderedDict()


def cache_get(url: str) -> Optional[Tuple[str, str]]:
    hit = _cache.get(url)
    if not hit:
        return None
    if time.monotonic() - hit[0] > CACHE_TTL_S:
        _cache.pop(url, None)
        return None
    _cache.move_to_end(url)
    return hit[1]


def cache_put(url: str, value: Tuple[str, str]) -> None:
    if len(value[1]) > CACHE_MAX_ENTRY_CHARS:
        return
    _cache[url] = (time.monotonic(), value)
    _cache.move_to_end(url)
    while len(_cache) > CACHE_MAX_ENTRIES:
        _cache.popitem(last=False)


def cache_clear() -> None:
    _cache.clear()


__all__ = ["html_to_markdown", "pdf_to_text", "extract", "cache_get", "cache_put", "cache_clear"]
