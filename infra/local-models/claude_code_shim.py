#!/usr/bin/env python3
"""
Minimal OpenAI-compatible chat-completions shim over the `claude` CLI's
headless print mode, so Claude Code can sit in the llm-council as a plain
"opinion" council member (no file/tool access - `--restricted` strips the
tools that run commands or code).

Must run on the HOST (not inside the backend container): it shells out to
the `claude` binary and needs the host user's Claude Code login/credentials,
neither of which exist inside the docker image.

Each request blocks on a real `claude -p` call (a few seconds, real API
cost - this is not free like the local Qwen model). There is no true
token-by-token streaming; a streaming request gets the full answer back as
a single SSE chunk, which is enough for llm-council's SSE parser.

Run:
    python3 infra/local-models/claude_code_shim.py

Optional env vars:
    CLAUDE_SHIM_PORT     - port to listen on (default 8600)
    CLAUDE_SHIM_MODEL    - --model alias/name to pass to `claude` (default: unset, uses the CLI's own default)
    CLAUDE_SHIM_SECRET - required: requests must send "Authorization: Bearer <secret>".
                       The shim refuses to start without it (or with the placeholder
                       "not-needed"), because every accepted request runs the CLI on
                       your account.
    CLAUDE_SHIM_HOST   - address to bind (default 0.0.0.0). Prefer the docker bridge
                       gateway (e.g. 172.17.0.1) so the backend container reaches it
                       via host.docker.internal while the LAN does not.
    CLAUDE_SHIM_ALLOW_NO_AUTH=1 - opt out of the secret requirement (trusted, isolated hosts only)
"""

import hmac
import json
import os
import subprocess
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("CLAUDE_SHIM_PORT", "8600"))
MODEL_ALIAS = os.getenv("CLAUDE_SHIM_MODEL")
SHARED_SECRET = os.getenv("CLAUDE_SHIM_SECRET")
HOST = os.getenv("CLAUDE_SHIM_HOST", "0.0.0.0")
ALLOW_NO_AUTH = os.getenv("CLAUDE_SHIM_ALLOW_NO_AUTH") == "1"
PLACEHOLDER_SECRETS = {"", "not-needed"}
CLAUDE_TIMEOUT_S = 180
MAX_BODY_BYTES = 8 * 1024 * 1024


def flatten_content(content):
    """OpenAI content may be a string, None, or a list of typed parts; the CLI takes text only."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                texts.append(str(part.get("text", "")))
            elif isinstance(part, dict) and part.get("type") == "image_url":
                texts.append("[image omitted]")
        return "\n".join(t for t in texts if t)
    return str(content)


def messages_to_prompt(messages):
    """Flatten an OpenAI-style messages array into a single prompt string."""
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = flatten_content(m.get("content", ""))
        if role == "system":
            parts.append(f"[System instructions]\n{content}")
        elif role == "assistant":
            parts.append(f"[Your previous turn]\n{content}")
        else:
            parts.append(content)
    return "\n\n".join(parts)


def run_claude(prompt):
    cmd = ["claude", "-p", "--restricted", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--output-format", "json"]
    if MODEL_ALIAS:
        cmd += ["--model", MODEL_ALIAS]
    # The prompt goes through stdin, not argv: a single argv item is capped at ~128 KB
    # on Linux (big round-table prompts would fail) and a prompt starting with "--"
    # would otherwise be parsed as a CLI flag.

    # Determine execution directory: CLAUDE_SHIM_CWD > WORKSPACE_DIR > cwd
    target_cwd = os.getenv("CLAUDE_SHIM_CWD") or os.getenv("WORKSPACE_DIR")
    if not target_cwd or not os.path.isdir(target_cwd):
        target_cwd = os.getcwd()

    result = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT_S,
        cwd=target_cwd,
        # A seat must never re-enter the council: the MCP server reads this guard.
        env={**os.environ, "LLM_COUNCIL_INVOCATION": "1"},
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude exited {result.returncode}: {result.stderr[:2000]}")

    data = json.loads(result.stdout)
    if data.get("is_error"):
        raise RuntimeError(f"claude reported an error: {data}")

    text = data.get("result", "")
    usage = data.get("usage", {})
    return text, {
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
    }, data.get("total_cost_usd")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[claude-shim] {self.address_string()} - {format % args}")

    def _unauthorized(self):
        self.send_response(401)
        self.end_headers()
        self.wfile.write(b'{"error":"unauthorized"}')

    def _check_auth(self):
        if ALLOW_NO_AUTH and not SHARED_SECRET:
            return True
        supplied = self.headers.get("Authorization", "")
        return hmac.compare_digest(supplied.encode(), f"Bearer {SHARED_SECRET}".encode())

    def do_POST(self):
        if self.path.rstrip("/") != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return

        if not self._check_auth():
            self._unauthorized()
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 <= length <= MAX_BODY_BYTES:
                raise ValueError("bad Content-Length")
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"invalid request body"}')
            return
        messages = body.get("messages", [])
        stream = bool(body.get("stream"))
        prompt = messages_to_prompt(messages)

        try:
            content, usage, cost_usd = run_claude(prompt)
        except Exception as e:
            print(f"[claude-shim] error: {e}")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": "local/claude-code",
                "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
            }
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())

            final_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": "local/claude-code",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": usage,
            }
            self.wfile.write(f"data: {json.dumps(final_chunk)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            payload = {
                "id": completion_id,
                "object": "chat.completion",
                "created": created,
                "model": "local/claude-code",
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
                ],
                "usage": usage,
            }
            body_bytes = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)

        if cost_usd is not None:
            print(f"[claude-shim] answered ({len(content)} chars, ${cost_usd:.4f})")


if __name__ == "__main__":
    if (SHARED_SECRET or "") in PLACEHOLDER_SECRETS and not ALLOW_NO_AUTH:
        raise SystemExit(
            "[claude-shim] refusing to start: set CLAUDE_SHIM_SECRET to a random value "
            "(or CLAUDE_SHIM_ALLOW_NO_AUTH=1 on an isolated host)"
        )
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[claude-shim] listening on {HOST}:{PORT} -> claude -p --restricted")
    server.serve_forever()
