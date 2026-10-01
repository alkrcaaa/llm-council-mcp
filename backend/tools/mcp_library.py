"""Curated MCP catalog: one-click install of vetted, version-pinned stdio servers.

Entries live in this file on purpose. A client can only pick an entry by id; it can never
supply the command, so installing from the library does not widen what the API can run
(user-supplied stdio commands stay behind MCP_ALLOW_STDIO). Every entry runs through
``uvx`` at an exact version.

Adding an entry: check the package on PyPI (maintainer, license, source repo, release
date), query OSV for the pinned version, read what the tools can reach, and put anything
risky in ``warnings``. Do not add servers whose tools read local files (e.g. markitdown's
``file://`` support would expose the backend container's data directory).
"""

import shutil
from typing import Any, Dict, List, Optional

from . import mcp_client

CATALOG: List[Dict[str, Any]] = [
    {
        "id": "fetch",
        "name": "Fetch",
        "category": "Research",
        "summary": "Fetch a web page and return it as markdown, with paging for long pages.",
        "package": "mcp-server-fetch",
        "version": "2026.8.18",
        "command": "uvx",
        "executable": "mcp-server-fetch",
        "maintainer": "Anthropic, PBC",
        "license": "MIT",
        "source": "https://github.com/modelcontextprotocol/servers/tree/main/src/fetch",
        "verified": "2026-10-01",
        "warnings": [
            "Runs inside the backend container and is not covered by the built-in SSRF guard, so it can "
            "reach services on the container network. Keep its tool on Ask.",
        ],
    },
    {
        "id": "arxiv",
        "name": "arXiv papers",
        "category": "Research",
        "summary": "Search arXiv, download a paper and read its full text. Complements the built-in "
                   "paper search, which only returns metadata.",
        "package": "arxiv-mcp-server",
        "version": "0.7.3",
        "command": "uvx",
        "executable": "arxiv-mcp-server",
        "maintainer": "Joseph Blazick",
        "license": "Apache-2.0",
        "source": "https://github.com/blazickjp/arxiv-mcp-server",
        "verified": "2026-10-01",
        "warnings": [
            "Exposes 19 tools and some keep state (download_paper, watch_topic). Enable only the "
            "read tools you need, such as search_papers and read_paper.",
            "Downloads papers into the backend container's disk. Single maintainer.",
        ],
    },
]


def _entry(entry_id: str) -> Optional[Dict[str, Any]]:
    return next((e for e in CATALOG if e["id"] == entry_id), None)


def _args(entry: Dict[str, Any]) -> List[str]:
    return ["--from", f"{entry['package']}=={entry['version']}", entry["executable"]]


def list_catalog() -> Dict[str, Any]:
    installed = {
        s["id"]: s for s in mcp_client.list_servers() if str(s.get("origin") or "").startswith("library:")
    }
    return {
        "runner_available": shutil.which("uvx") is not None,
        "entries": [
            {**e, "pinned": f"{e['package']}=={e['version']}", "installed": e["id"] in installed}
            for e in CATALOG
        ],
    }


def install(entry_id: str) -> Dict[str, Any]:
    """Add the catalog entry as a server (all of its tools start as 'deny'). Raises McpError."""
    entry = _entry(entry_id)
    if not entry:
        raise mcp_client.McpError(f"unknown library entry '{entry_id}'")
    if shutil.which(entry["command"]) is None:
        raise mcp_client.McpError(f"'{entry['command']}' is not installed on the backend")
    return mcp_client.add_server(
        {
            "id": entry["id"],
            "name": entry["name"],
            "transport": "stdio",
            "command": entry["command"],
            "args": _args(entry),
        },
        origin=f"library:{entry['id']}",
    )
