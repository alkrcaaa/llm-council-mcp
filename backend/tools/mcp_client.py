"""External MCP servers: storage, per-tool policy, discovery, calls and human approvals.

Servers live in ``DATA_ROOT/mcp_servers.json``. Every discovered tool starts as ``deny``;
the user opts tools in as ``auto`` (runs freely) or ``ask`` (each call needs approval).
A connection is opened per operation (discovery or call), so there is no process or
session lifecycle to leak; the cost is a spawn per stdio call.

stdio servers run a command inside the backend's environment, so creating one is refused
unless ``MCP_ALLOW_STDIO=1``. Secrets (headers, env values) are never returned by the API.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from ..config import DATA_ROOT

logger = logging.getLogger("llm_council.mcp")

PREFIX = "mcp__"
POLICIES = ("auto", "ask", "deny")
MAX_SERVERS = 20
MAX_TOOLS_PER_SERVER = 100
MAX_EXPOSED_NAME = 64  # OpenAI-style function name limit
MAX_SCHEMA_CHARS = 20000
CONNECT_TIMEOUT_S = 30.0
APPROVAL_TIMEOUT_S = 120.0

# No "__": it separates server id from tool name, so ids "a" + tool "b__c" and "a__b" + "c" would collide.
_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]|_(?!_)){0,31}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_lock = threading.Lock()


def servers_file() -> str:
    return os.path.join(DATA_ROOT, "mcp_servers.json")


class McpError(Exception):
    """User-facing configuration or connection problem."""


def stdio_allowed() -> bool:
    return os.getenv("MCP_ALLOW_STDIO", "").strip().lower() in ("1", "true", "yes")


# ---------------------------------------------------------------- storage

def _load_strict() -> Dict[str, Dict[str, Any]]:
    """Missing file = no servers. An unreadable or corrupt file raises: writers must never
    rebuild the store from an empty dict and overwrite every stored token."""
    try:
        with open(servers_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise McpError(f"{servers_file()} is unreadable: {type(e).__name__}") from e
    servers = data.get("servers") if isinstance(data, dict) else None
    return servers if isinstance(servers, dict) else {}


def _load() -> Dict[str, Dict[str, Any]]:
    """Read path for chat and listings: a broken store must not break a conversation."""
    try:
        return _load_strict()
    except McpError as e:
        logger.error("%s", e)
        return {}


def _save(servers: Dict[str, Dict[str, Any]]) -> None:
    os.makedirs(DATA_ROOT, exist_ok=True)
    path = servers_file()
    tmp = f"{path}.tmp.{os.getpid()}"
    # Owner-only: the file holds header tokens and env secrets in plaintext.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)  # a leftover tmp file keeps its old mode otherwise
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"servers": servers}, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def exposed_name(server_id: str, tool: str) -> str:
    return f"{PREFIX}{server_id}__{tool}"


def redact_server(rec: Dict[str, Any]) -> Dict[str, Any]:
    """API-safe copy: header/env values never leave the backend, only which names are set."""
    safe = {k: v for k, v in rec.items() if k not in ("headers", "env", "tools")}
    safe["headers_set"] = sorted((rec.get("headers") or {}).keys())
    safe["env_set"] = sorted((rec.get("env") or {}).keys())
    safe["tools"] = [
        {
            "name": name,
            "exposed_name": exposed_name(rec["id"], name),
            "description": t.get("description", ""),
            "policy": t.get("policy", "deny"),
            "definition_changed": bool(t.get("definition_changed")),
        }
        for name, t in sorted((rec.get("tools") or {}).items())
    ]
    return safe


def list_servers() -> List[Dict[str, Any]]:
    with _lock:
        return [redact_server(r) for r in _load().values()]


def _clean_kv(raw: Any, what: str, key_re: re.Pattern) -> Dict[str, str]:
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        raise McpError(f"{what} must be an object")
    out: Dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not key_re.match(k) or not isinstance(v, str):
            raise McpError(f"invalid {what} entry: {k!r}")
        out[k] = v
    return out


_HEADER_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def _validate_transport(rec: Dict[str, Any]) -> None:
    if rec["transport"] == "http":
        url = rec.get("url") or ""
        if not re.match(r"^https?://[^\s]+$", url):
            raise McpError("url must be an http(s) URL")
    elif rec["transport"] == "stdio":
        if not stdio_allowed():
            raise McpError("stdio servers are disabled; set MCP_ALLOW_STDIO=1 on the backend to allow them")
        if not rec.get("command") or not isinstance(rec["command"], str):
            raise McpError("command is required for stdio servers")
        if not isinstance(rec.get("args"), list) or not all(isinstance(a, str) for a in rec["args"]):
            raise McpError("args must be a list of strings")
    else:
        raise McpError("transport must be 'http' or 'stdio'")


def add_server(data: Dict[str, Any]) -> Dict[str, Any]:
    server_id = str(data.get("id") or "").strip().lower()
    if not _ID_RE.match(server_id):
        raise McpError("id must be 1-32 chars of a-z, 0-9, '_' or '-'")
    rec: Dict[str, Any] = {
        "id": server_id,
        "name": str(data.get("name") or server_id)[:80],
        "transport": data.get("transport"),
        "enabled": bool(data.get("enabled", True)),
        "url": data.get("url") or "",
        "headers": _clean_kv(data.get("headers"), "headers", _HEADER_RE),
        "command": data.get("command") or "",
        "args": data.get("args") or [],
        "env": _clean_kv(data.get("env"), "env", _ENV_KEY_RE),
        "tools": {},
        "last_refresh": None,
        "last_error": None,
    }
    _validate_transport(rec)
    with _lock:
        servers = _load_strict()
        if server_id in servers:
            raise McpError(f"server '{server_id}' already exists")
        if len(servers) >= MAX_SERVERS:
            raise McpError(f"at most {MAX_SERVERS} servers")
        servers[server_id] = rec
        _save(servers)
    return redact_server(rec)


def update_server(server_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Patch name/enabled/url/args/command, merge headers/env (empty value deletes a name,
    omitted names keep their stored value) and set tool policies."""
    with _lock:
        servers = _load_strict()
        rec = servers.get(server_id)
        if not rec:
            raise McpError(f"unknown server '{server_id}'")
        if "name" in patch:
            rec["name"] = str(patch["name"])[:80]
        if "enabled" in patch:
            rec["enabled"] = bool(patch["enabled"])
        for field in ("url", "command"):
            if field in patch:
                rec[field] = patch[field] or ""
        if "args" in patch:
            rec["args"] = patch["args"] or []
        for field, key_re in (("headers", _HEADER_RE), ("env", _ENV_KEY_RE)):
            if field in patch:
                merged = dict(rec.get(field) or {})
                for k, v in _clean_kv(patch[field], field, key_re).items():
                    if v == "":
                        merged.pop(k, None)
                    else:
                        merged[k] = v
                rec[field] = merged
        for tool, policy in (patch.get("tool_policies") or {}).items():
            if policy not in POLICIES:
                raise McpError(f"policy must be one of {', '.join(POLICIES)}")
            if tool not in rec["tools"]:
                raise McpError(f"unknown tool '{tool}'; refresh the server first")
            rec["tools"][tool]["policy"] = policy
        _validate_transport(rec)
        _save(servers)
        return redact_server(rec)


def delete_server(server_id: str) -> bool:
    with _lock:
        servers = _load_strict()
        if server_id not in servers:
            return False
        del servers[server_id]
        _save(servers)
        return True


# ---------------------------------------------------------------- lookup for the tool loop

def resolve(exposed: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """(server record, original tool name) for an exposed name, or None."""
    if not exposed.startswith(PREFIX):
        return None
    for rec in _load().values():
        for tool in rec.get("tools") or {}:
            if exposed_name(rec["id"], tool) == exposed:
                return rec, tool
    return None


def policy_for(exposed: str) -> Optional[str]:
    """None for non-MCP names. Unknown or disabled MCP tools are 'deny'."""
    if not exposed.startswith(PREFIX):
        return None
    found = resolve(exposed)
    if not found:
        return "deny"
    rec, tool = found
    if not rec.get("enabled"):
        return "deny"
    policy = rec["tools"][tool].get("policy", "deny")
    return policy if policy in POLICIES else "deny"


def get_tool_definitions() -> List[Dict[str, Any]]:
    """OpenAI-format definitions for every enabled, non-denied MCP tool (read from the
    stored discovery result, no network)."""
    defs: List[Dict[str, Any]] = []
    for rec in _load().values():
        if not rec.get("enabled"):
            continue
        for tool, t in (rec.get("tools") or {}).items():
            if t.get("policy", "deny") not in ("auto", "ask"):
                continue
            desc = (t.get("description") or "")[:500]
            defs.append({
                "type": "function",
                "function": {
                    "name": exposed_name(rec["id"], tool),
                    "description": f"[MCP server {rec['name']}] {desc}".strip(),
                    "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
                },
            })
    return defs


# ---------------------------------------------------------------- connections

@asynccontextmanager
async def _session(rec: Dict[str, Any]) -> AsyncIterator[Any]:
    from mcp import ClientSession  # lazy: the backend boots without the SDK

    if rec["transport"] == "stdio":
        from mcp.client.stdio import StdioServerParameters, stdio_client

        if not stdio_allowed():
            raise McpError("stdio servers are disabled (MCP_ALLOW_STDIO)")
        params = StdioServerParameters(
            command=rec["command"], args=list(rec.get("args") or []), env=dict(rec.get("env") or {}) or None,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    else:
        from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

        http_client = create_mcp_http_client(headers=dict(rec.get("headers") or {}) or None)
        async with http_client:
            async with streamable_http_client(rec["url"], http_client=http_client) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    yield session


def _fingerprint(meta: Dict[str, Any]) -> str:
    blob = json.dumps([meta["description"], meta["input_schema"]], sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


_URL_USERINFO = re.compile(r"(://)[^/\s@]+@")
_QUERY_VALUE = re.compile(r"([?&][^=\s&]+=)[^&\s]+")


def _scrub(text: str) -> str:
    """Drop URL credentials and query values from an error before it is stored or logged."""
    return _QUERY_VALUE.sub(r"\1***", _URL_USERINFO.sub(r"\1***@", text))


def _schema(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict) and len(json.dumps(raw, default=str)) <= MAX_SCHEMA_CHARS:
        return raw
    return {"type": "object", "properties": {}}


async def refresh_server(server_id: str) -> Dict[str, Any]:
    """Connect, list tools and store them. New tools start as 'deny'; existing policies stay."""
    rec = _load_strict().get(server_id)
    if not rec:
        raise McpError(f"unknown server '{server_id}'")
    error: Optional[str] = None
    found: Dict[str, Dict[str, Any]] = {}
    try:
        async def _discover() -> None:
            async with _session(rec) as session:
                result = await session.list_tools()
                for t in result.tools[:MAX_TOOLS_PER_SERVER]:
                    # Never truncate: two long names would collapse into one and share a policy.
                    if _NAME_RE.match(t.name) and len(exposed_name(server_id, t.name)) <= MAX_EXPOSED_NAME:
                        meta = {
                            "description": (t.description or "")[:1000],
                            "input_schema": _schema(t.input_schema),
                        }
                        meta["fingerprint"] = _fingerprint(meta)
                        found[t.name] = meta
        await asyncio.wait_for(_discover(), timeout=CONNECT_TIMEOUT_S)
    except McpError:
        raise
    except asyncio.TimeoutError:
        error = f"timed out after {CONNECT_TIMEOUT_S:.0f}s"
    except Exception as e:  # SDK, OS and network errors all surface the same way
        error = _scrub(f"{type(e).__name__}: {e}")[:300]
        logger.warning("MCP refresh failed for %s: %s", server_id, error)

    with _lock:
        servers = _load_strict()
        current = servers.get(server_id)
        if not current:
            raise McpError(f"unknown server '{server_id}'")
        current["last_error"] = error
        if error is None:
            old = current.get("tools") or {}
            tools: Dict[str, Dict[str, Any]] = {}
            for name, meta in found.items():
                prev = old.get(name) or {}
                # A changed description or schema is new, unreviewed text that goes straight
                # into model prompts: it must be opted into again.
                same = prev.get("fingerprint") == meta["fingerprint"]
                tools[name] = {
                    **meta,
                    "policy": prev.get("policy", "deny") if same else "deny",
                    "definition_changed": bool(prev) and not same,
                }
            current["tools"] = tools
            current["last_refresh"] = int(time.time())
        _save(servers)
        return redact_server(current)


def _result_text(result: Any) -> str:
    parts: List[str] = []
    for block in getattr(result, "content", None) or []:
        kind = getattr(block, "type", "")
        if kind == "text":
            parts.append(block.text)
        elif kind == "resource" and getattr(getattr(block, "resource", None), "text", None):
            parts.append(block.resource.text)
        else:
            parts.append(f"[{kind or 'non-text'} content omitted]")
    if not parts and getattr(result, "structured_content", None):
        parts.append(json.dumps(result.structured_content, default=str))
    return "\n".join(parts)


async def call_tool(exposed: str, arguments: Dict[str, Any]) -> str:
    """Call an MCP tool. Refuses denied/unknown tools; approval for 'ask' happens in the loop."""
    if policy_for(exposed) not in ("auto", "ask"):
        return f"Error: MCP tool '{exposed}' is not enabled."
    rec, tool = resolve(exposed)  # type: ignore[misc]  # policy_for proved it exists
    try:
        async with _session(rec) as session:
            result = await session.call_tool(tool, arguments)
    except Exception as e:
        return f"Error: MCP server '{rec['id']}' call failed: {type(e).__name__}"
    text = _result_text(result)
    return f"Error: {text or 'tool reported an error'}" if getattr(result, "is_error", False) else text


# ---------------------------------------------------------------- approvals

_approvals: Dict[str, "asyncio.Future[bool]"] = {}


def new_approval() -> Tuple[str, "asyncio.Future[bool]"]:
    approval_id = uuid.uuid4().hex
    fut: "asyncio.Future[bool]" = asyncio.get_running_loop().create_future()
    _approvals[approval_id] = fut
    return approval_id, fut


def resolve_approval(approval_id: str, approve: bool) -> bool:
    """False if the id is unknown or already decided."""
    fut = _approvals.get(approval_id)
    if fut is None or fut.done():
        return False
    fut.set_result(bool(approve))
    return True


def discard_approval(approval_id: str) -> None:
    _approvals.pop(approval_id, None)


async def wait_approval(fut: "asyncio.Future[bool]") -> bool:
    """True only on an explicit approval; timeout counts as denied."""
    try:
        return await asyncio.wait_for(fut, timeout=APPROVAL_TIMEOUT_S)
    except asyncio.TimeoutError:
        return False
