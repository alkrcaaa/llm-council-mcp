"""MCP Bridge and Unified Tool Execution Engine.

Bridges:
1. Built-in high-leverage tools (web search, web fetch, GitHub scout, package scout, workspace diff/read).
2. External HTTP/SSE MCP servers (fetch, playwright, code-review-graph).
3. Translates tools to standard OpenAI function-calling format.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from .builtin import (
    tool_github_scout,
    tool_package_scout,
    tool_web_fetch,
    tool_web_search,
    tool_workspace_git_diff,
    tool_workspace_read_file,
)

logger = logging.getLogger("llm_council.tools")

# Determine host base for MCP services
IN_CONTAINER = os.path.exists("/.dockerenv") or os.path.exists("/app/backend")
MCP_HOST = "host.docker.internal" if IN_CONTAINER else "localhost"

# Known HTTP MCP Server Endpoints
MCP_SERVERS = {
    "fetch": f"http://{MCP_HOST}:8935/mcp",
    "playwright": f"http://{MCP_HOST}:8932/mcp",
    "code-review-graph": f"http://{MCP_HOST}:8931/mcp",
}

# OpenAI-compatible function definitions for built-in tools
BUILTIN_TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the live web for recent technical documentation, RFCs, articles, or libraries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Specific search terms or keywords.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default: 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    "web_fetch": {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch a webpage URL and extract clean, readable markdown content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "HTTP or HTTPS URL to fetch.",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to return (default: 4000).",
                        "default": 4000,
                    },
                },
                "required": ["url"],
            },
        },
    },
    "github_scout": {
        "type": "function",
        "function": {
            "name": "github_scout",
            "description": "Inspect a GitHub repository ('owner/repo') or search for top open-source repositories matching a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_or_repo": {
                        "type": "string",
                        "description": "Either 'owner/repo' path or a search query string.",
                    },
                },
                "required": ["query_or_repo"],
            },
        },
    },
    "package_scout": {
        "type": "function",
        "function": {
            "name": "package_scout",
            "description": "Search PyPI and NPM package registries for libraries, published versions, and licenses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_query": {
                        "type": "string",
                        "description": "Package name or keyword (e.g. 'pydantic', 'fastapi', 'zod').",
                    },
                },
                "required": ["package_query"],
            },
        },
    },
    "workspace_read_file": {
        "type": "function",
        "function": {
            "name": "workspace_read_file",
            "description": "Read a source code file from the current project or workspace to review implementations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file (e.g. 'src/index.ts' or 'backend/main.py').",
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum lines to read (default: 150).",
                        "default": 150,
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    "workspace_git_diff": {
        "type": "function",
        "function": {
            "name": "workspace_git_diff",
            "description": "Inspect uncommitted git status and diffs in the project workspace to evaluate code changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum diff characters to return (default: 3500).",
                        "default": 3500,
                    },
                },
            },
        },
    },
}


async def call_http_mcp_tool(server_url: str, tool_name: str, arguments: Dict[str, Any], timeout: float = 12.0) -> Optional[str]:
    """Call an MCP tool over HTTP/SSE JSON-RPC transport."""
    try:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
            "id": 1,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(server_url, json=payload, headers=headers)
            if resp.status_code != 200:
                return None

            # SSE streams format lines as 'data: {...}'
            content = resp.text
            for line in content.splitlines():
                if line.startswith("data:"):
                    json_str = line[5:].strip()
                    try:
                        data = json.loads(json_str)
                        res = data.get("result", {})
                        content_list = res.get("content", [])
                        if content_list and isinstance(content_list, list):
                            texts = [c.get("text", "") for c in content_list if c.get("type") == "text"]
                            return "\n".join(texts)
                    except Exception:
                        continue
    except Exception as e:
        logger.debug(f"MCP HTTP call failed for {tool_name} on {server_url}: {e}")
    return None


async def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    target_workspace: Optional[str] = None,
) -> str:
    """Execute a tool by name and return a string result suitable for LLM tool_message.

    Args:
        tool_name: Name of the tool to execute
        arguments: Dict of keyword arguments passed by LLM
        target_workspace: Current workspace name context
    """
    try:
        # 1. Built-in tools
        if tool_name == "web_search":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 5)
            return await tool_web_search(query, limit=limit)

        if tool_name == "web_fetch":
            url = arguments.get("url", "")
            max_chars = arguments.get("max_chars", 4000)
            # Try external fetch MCP server first if available, fallback to builtin
            mcp_res = await call_http_mcp_tool(MCP_SERVERS["fetch"], "fetch_readable", {"url": url})
            if mcp_res:
                return f"### Content from: {url}\n\n{mcp_res[:max_chars]}"
            return await tool_web_fetch(url, max_chars=max_chars)

        if tool_name == "github_scout":
            query_or_repo = arguments.get("query_or_repo", "")
            return await tool_github_scout(query_or_repo)

        if tool_name == "package_scout":
            package_query = arguments.get("package_query", "")
            return await tool_package_scout(package_query)

        if tool_name == "workspace_read_file":
            file_path = arguments.get("file_path", "")
            max_lines = arguments.get("max_lines", 150)
            return await tool_workspace_read_file(file_path, target_workspace=target_workspace, max_lines=max_lines)

        if tool_name == "workspace_git_diff":
            max_chars = arguments.get("max_chars", 3500)
            return await tool_workspace_git_diff(target_workspace=target_workspace, max_chars=max_chars)

        return f"Error: Tool '{tool_name}' is not recognized."
    except Exception as e:
        return f"Error executing tool '{tool_name}': {str(e)}"


def get_tool_definitions(tool_names: List[str]) -> List[Dict[str, Any]]:
    """Return OpenAI-compatible tool specifications for a list of tool names."""
    defs = []
    for name in tool_names:
        if name in BUILTIN_TOOL_SCHEMAS:
            defs.append(BUILTIN_TOOL_SCHEMAS[name])
    return defs
