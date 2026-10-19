import asyncio

import httpx
import pytest
from fastapi import FastAPI, Request

from app.cloud_demo_guard import CloudDemoGuard


def client_app(limit=2):
    inner = FastAPI()

    @inner.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
    async def echo(path: str, request: Request):
        return {"path": path, "body": await request.json() if request.method == "POST" else None}

    clock = [100.0]
    guarded = CloudDemoGuard(inner, chat_limit=limit, clock=lambda: clock[0])
    return guarded, clock


def test_demo_allowlist_and_identity_boundary():
    async def run():
        app, _ = client_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://demo") as client:
            for path in ["/admin", "/admin/", "/api/admin/logs", "/openapi.json", "/docs", "/design-lab", "/.env", "/api/study/session/start"]:
                assert (await client.get(path)).status_code == 404
                assert (await client.post(path, json={})).status_code == 404
            for path in ["/", "/chat/", "/healthz", "/_next/static/test.js", "/chat/index.txt", "/__next.__PAGE__.txt"]:
                assert (await client.get(path)).status_code == 200
            assert (await client.get("/admin/index.txt")).status_code == 404
            assert (await client.post("/api/chat", json={"question": "test", "sessionId": "P01"})).status_code == 400
            assert (await client.post("/api/chat", content="[1,2]")).status_code == 400
            assert (await client.post("/api/chat", content="x" * 16001)).status_code == 413
            response = await client.post("/api/chat", json={"question": "test"})
            assert response.status_code == 200
            assert response.json()["body"] == {"question": "test"}
    asyncio.run(run())


def test_chat_limit_cooldown_and_retryable_errors():
    async def run():
        app, clock = client_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://demo") as client:
            assert (await client.post("/api/chat", json={})).status_code == 200
            response = await client.post("/api/chat", json={})
            assert response.status_code == 429
            assert response.json()["detail"]["retryable"] is True
            clock[0] += 11
            assert (await client.post("/api/chat", json={})).status_code == 200
            clock[0] += 3600
            assert (await client.post("/api/chat", json={})).status_code == 429
            assert (await client.post("/api/study/log-event", json={})).status_code == 200
    asyncio.run(run())


def test_event_rate_limit():
    async def run():
        app, clock = client_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://demo") as client:
            for _ in range(120):
                assert (await client.post("/api/study/log-event", json={})).status_code == 200
            assert (await client.post("/api/study/log-event", json={})).status_code == 429
            clock[0] += 61
            assert (await client.post("/api/study/log-event", json={})).status_code == 200
    asyncio.run(run())


def test_only_one_answer_runs_at_once_and_failures_release_slot():
    async def run():
        started, release = asyncio.Event(), asyncio.Event()

        async def inner(scope, receive, send):
            started.set()
            await release.wait()
            raise RuntimeError("test failure")

        clock = [100.0]
        app = CloudDemoGuard(inner, clock=lambda: clock[0])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://demo") as client:
            first = asyncio.create_task(client.post("/api/chat", json={}))
            await started.wait()
            clock[0] += 11
            assert (await client.post("/api/chat", json={})).status_code == 429
            release.set()
            with pytest.raises(RuntimeError):
                await first
            assert not app.chat_busy
    asyncio.run(run())
