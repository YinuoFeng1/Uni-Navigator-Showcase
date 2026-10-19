"""Public demo boundary; the research API remains unchanged behind it."""

import asyncio
import json
import time
import re
from collections import deque

from starlette.responses import JSONResponse


class CloudDemoGuard:
    allowed_posts = {
        "/api/chat", "/api/study/log-event", "/api/study/evidence-use",
        "/api/study/feedback",
    }

    def __init__(self, app, *, chat_limit: int = 30, clock=time.monotonic):
        if not 1 <= chat_limit <= 100:
            raise ValueError("Cloud demo chat limit must be between 1 and 100")
        self.app = app
        self.chat_limit = chat_limit
        self.clock = clock
        self.calls = deque()
        self.chats = 0
        self.last_chat = float("-inf")
        self.chat_busy = False
        self.lock = asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        method = scope["method"]
        is_post = method == "POST" and path in self.allowed_posts
        is_read = method in {"GET", "HEAD"} and (
            path in {"/", "/chat", "/chat/", "/healthz", "/favicon.ico"}
            or path.startswith("/_next/static/")
            or re.fullmatch(r"/(chat/)?(?:index|__next\.[A-Za-z0-9_.]+)\.txt", path) is not None
        )
        if not (is_post or is_read):
            return await JSONResponse({"detail": "Not available in this demo."}, 404)(scope, receive, send)
        async def safe_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-robots-tag", b"noindex, nofollow, noarchive"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                ]
            await send(message)

        if not is_post:
            return await self.app(scope, receive, safe_send)

        # Bound bodies before JSON parsing, including chunked uploads.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > 16000:
                return await JSONResponse({"detail": "Request too large."}, 413)(scope, receive, send)
            if not message.get("more_body"):
                break
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeError):
            payload = None
        if not isinstance(payload, dict) or any(
            payload.get(key) for key in ("sessionId", "participantLabel", "participantId", "taskId")
        ):
            return await JSONResponse({"detail": "Demo requests cannot include research identities."}, 400)(scope, receive, send)

        chat = path == "/api/chat"
        async with self.lock:
            now = self.clock()
            while self.calls and self.calls[0] <= now - 60:
                self.calls.popleft()
            limited = len(self.calls) >= 120 or (chat and (
                self.chat_busy or self.chats >= self.chat_limit or now - self.last_chat < 10
            ))
            if not limited:
                self.calls.append(now)
                if chat:
                    self.chat_busy = True
                    self.chats += 1
                    self.last_chat = now
        if limited:
            return await JSONResponse({"detail": {
                "message": "Demo usage limit reached or another answer is running. Please try later.",
                "failureCategory": "demo_rate_limit", "retryable": True,
            }}, 429, headers={"Retry-After": "60"})(scope, receive, send)

        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        try:
            await self.app(scope, replay, safe_send)
        finally:
            if chat:
                async with self.lock:
                    self.chat_busy = False
