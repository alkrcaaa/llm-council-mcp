"""Request body cap and a small rate limit for endpoints that cost money or make outbound calls."""

import os
import re
import time
from collections import defaultdict, deque

MAX_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(2_000_000)))
RATE_LIMIT_PER_MINUTE = int(os.getenv("COSTLY_RATE_LIMIT_PER_MINUTE", "60"))

# POST endpoints that spend model tokens or fetch remote URLs.
_COSTLY = re.compile(
    r"^/api/("
    r"conversations/[^/]+/message(/stream)?"
    r"|research/scout"
    r"|skills/import(/.*)?"
    r"|providers/(test|fetch-models)"
    r"|routing/classify"
    r"|cache/search"
    r")$"
)


def is_costly(method: str, path: str) -> bool:
    return method == "POST" and bool(_COSTLY.match(path))


class RateLimiter:
    """Sliding one-minute window per client key."""

    def __init__(self, limit: int = RATE_LIMIT_PER_MINUTE, window: float = 60.0):
        self.limit = limit
        self.window = window
        self._hits: dict = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


async def _reject(send, status: int, detail: str, headers=()):
    body = ('{"detail":"%s"}' % detail).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), *headers],
    })
    await send({"type": "http.response.body", "body": body})


class LimitsMiddleware:
    """Pure ASGI, so a streaming body is counted as it arrives instead of buffered first."""

    def __init__(self, app, max_body: int = MAX_BODY_BYTES, limiter: RateLimiter | None = None):
        self.app = app
        self.max_body = max_body
        self.limiter = limiter or RateLimiter()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)

        if is_costly(scope["method"], scope["path"]):
            client = (scope.get("client") or ("unknown", 0))[0]
            if not self.limiter.allow(client):
                return await _reject(send, 429, "Too many requests", [(b"retry-after", b"60")])

        declared = dict(scope["headers"]).get(b"content-length")
        if declared and declared.isdigit() and int(declared) > self.max_body:
            return await _reject(send, 413, "Request body too large")

        received = 0
        too_large = False

        async def counting_receive():
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body:
                    too_large = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def guarded_send(message):
            # A chunked upload can overrun after the app has started reading; whatever the
            # app answers for the truncated body is replaced by a 413.
            if too_large:
                if message["type"] == "http.response.start":
                    await _reject(send, 413, "Request body too large")
                return
            await send(message)

        await self.app(scope, counting_receive, guarded_send)
