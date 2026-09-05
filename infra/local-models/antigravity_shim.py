#!/usr/bin/env python3
"""
Minimal OpenAI-compatible chat-completions shim over the `agy` (Antigravity)
CLI's headless print mode, so Antigravity can sit in the llm-council as a
plain "opinion" council member (no file/tool access - `--sandbox` restricts
the terminal).

Must run on the HOST (not inside the backend container): it shells out to
the `agy` binary and needs the host user's Antigravity login, neither of
which exist inside the docker image.

Each request blocks on a real `agy --print` call (a few seconds, real API
cost). There is no true token-by-token streaming; a streaming request gets
the full answer back as a single SSE chunk, which is enough for
llm-council's SSE parser.

Run:
    python3 infra/local-models/antigravity_shim.py

Optional env vars:
    ANTIGRAVITY_SHIM_PORT   - port to listen on (default 8601)
    ANTIGRAVITY_SHIM_MODEL  - --model to pass to `agy` (default: unset, uses the CLI's own default)
    ANTIGRAVITY_SHIM_SECRET - if set, requests must send "Authorization: Bearer <secret>"
                              (unset = open to anyone who can reach the port; fine on a
                              trusted LAN, but note every accepted request spends real
                              API credit on your account)
"""

import json
import os
import subprocess
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("ANTIGRAVITY_SHIM_PORT", "8601"))
MODEL = os.getenv("ANTIGRAVITY_SHIM_MODEL")
SHARED_SECRET = os.getenv("ANTIGRAVITY_SHIM_SECRET")
AGY_TIMEOUT_S = 180


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


def run_agy(prompt):
    # agy's flag parser consumes the very next token as --print's value, so
    # the prompt must be attached with "=" as a single argv item.
    cmd = ["agy", "--sandbox", "--output-format", "json"]
    if MODEL:
        cmd += ["--model", MODEL]
    cmd.append(f"--print={prompt}")

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=AGY_TIMEOUT_S
    )
    if result.returncode != 0:
        raise RuntimeError(f"agy exited {result.returncode}: {result.stderr[:2000]}")

    data = json.loads(result.stdout)
    if data.get("status") != "SUCCESS":
        raise RuntimeError(f"agy reported an error: {data}")

    text = data.get("response", "")
    usage = data.get("usage", {})
    return text, {
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[antigravity-shim] {self.address_string()} - {format % args}")

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
            content, usage = run_agy(prompt)
        except Exception as e:
            print(f"[antigravity-shim] error: {e}")
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
                "model": "local/antigravity",
                "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
            }
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())

            final_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": "local/antigravity",
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
                "model": "local/antigravity",
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

        print(f"[antigravity-shim] answered ({len(content)} chars, {usage['total_tokens']} tokens)")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[antigravity-shim] listening on 0.0.0.0:{PORT} -> agy --sandbox --print")
    if not SHARED_SECRET:
        print("[antigravity-shim] WARNING: no ANTIGRAVITY_SHIM_SECRET set - anyone who can reach "
              "this port can spend your API credit. Fine on a trusted LAN only.")
    server.serve_forever()
