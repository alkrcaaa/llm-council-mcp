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
    CLAUDE_SHIM_SECRET   - if set, requests must send "Authorization: Bearer <secret>"
                           (unset = open to anyone who can reach the port; fine on a
                           trusted LAN, but note every accepted request spends real
                           Claude API credit on your account)
"""

import json
import os
import subprocess
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("CLAUDE_SHIM_PORT", "8600"))
MODEL_ALIAS = os.getenv("CLAUDE_SHIM_MODEL")
SHARED_SECRET = os.getenv("CLAUDE_SHIM_SECRET")
CLAUDE_TIMEOUT_S = 180


def messages_to_prompt(messages):
    """Flatten an OpenAI-style messages array into a single prompt string."""
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            parts.append(f"[System instructions]\n{content}")
        elif role == "assistant":
            parts.append(f"[Your previous turn]\n{content}")
        else:
            parts.append(content)
    return "\n\n".join(parts)


def run_claude(prompt):
    cmd = ["claude", "-p", "--restricted", "--strict-mcp-config", "--mcp-config", "{}", "--output-format", "json"]
    if MODEL_ALIAS:
        cmd += ["--model", MODEL_ALIAS]
    cmd.append(prompt)

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT_S
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
        if not SHARED_SECRET:
            return True
        return self.headers.get("Authorization") == f"Bearer {SHARED_SECRET}"

    def do_POST(self):
        if self.path.rstrip("/") != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return

        if not self._check_auth():
            self._unauthorized()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
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
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[claude-shim] listening on 0.0.0.0:{PORT} -> claude -p --restricted")
    if not SHARED_SECRET:
        print("[claude-shim] WARNING: no CLAUDE_SHIM_SECRET set - anyone who can reach "
              "this port can spend your Claude API credit. Fine on a trusted LAN only.")
    server.serve_forever()
