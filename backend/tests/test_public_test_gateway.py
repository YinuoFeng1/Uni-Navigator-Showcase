import importlib.util
from io import BytesIO
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import socket
import subprocess
from threading import Thread
import time
from urllib.error import HTTPError, URLError

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
CADDY = ROOT / ".tools/bin/caddy"


@pytest.fixture
def public_test():
    spec = importlib.util.spec_from_file_location("public_test", ROOT / "scripts/public_test.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_private_access_file_and_same_origin_build(tmp_path, monkeypatch, public_test):
    module = public_test
    path = tmp_path / "access.json"
    monkeypatch.setattr(module, "ACCESS", path)
    values = module.credentials()
    assert values == module.credentials()
    assert set(values) == {"researcher"}
    assert len(values["researcher"]["password"]) >= 24
    assert set(json.loads(path.read_text())) == {"researcher"}
    assert path.stat().st_mode & 0o777 == 0o600
    node = tmp_path / "node"
    node.touch(mode=0o700)
    monkeypatch.setenv("CODEX_NODE_BIN", str(node))
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000")
    env = module.application_env()
    assert env["NEXT_PUBLIC_API_BASE_URL"] == ""
    assert env["NEXT_BUILD_DIR"] == ".next-public"
    assert env["CODEX_NODE_BIN"] == str(node.resolve())


def test_existing_researcher_password_is_preserved(tmp_path, monkeypatch, public_test):
    path = tmp_path / "access.json"
    researcher = {"username": "researcher", "password": "existing-researcher-secret"}
    path.write_text(json.dumps({"researcher": researcher, "participant": {"password": "unused"}}))
    monkeypatch.setattr(public_test, "ACCESS", path)
    assert public_test.credentials() == {"researcher": researcher}


def test_invalid_node_fails_before_build(tmp_path, monkeypatch, public_test):
    missing = tmp_path / ".home/.cache/node"
    monkeypatch.setenv("CODEX_NODE_BIN", str(missing))
    monkeypatch.setattr(public_test, "supervisor_pid", lambda: None)

    def unexpected_build(*args, **kwargs):
        pytest.fail("Invalid Node must be rejected before the build or supervisor starts")

    monkeypatch.setattr(public_test.subprocess, "run", unexpected_build)
    monkeypatch.setattr(public_test.subprocess, "Popen", unexpected_build)
    with pytest.raises(RuntimeError, match="VS Code workspace HOME"):
        public_test.start()


def test_non_executable_node_is_rejected(tmp_path, monkeypatch, public_test):
    node = tmp_path / "node"
    node.touch(mode=0o600)
    monkeypatch.setenv("CODEX_NODE_BIN", str(node))
    with pytest.raises(RuntimeError, match="not executable"):
        public_test.application_env()


def test_node_wrapper_is_rejected(tmp_path, monkeypatch, public_test):
    wrapper = tmp_path / ".tools/bin/node"
    wrapper.parent.mkdir(parents=True)
    wrapper.touch(mode=0o700)
    monkeypatch.setattr(public_test, "ROOT", tmp_path)
    monkeypatch.delenv("CODEX_NODE_BIN", raising=False)
    monkeypatch.setattr(public_test.shutil, "which", lambda name: str(wrapper))
    with pytest.raises(RuntimeError, match="real Node executable"):
        public_test.application_env()


def test_node_path_is_resolved_without_workspace_home(tmp_path, monkeypatch, public_test):
    node = tmp_path / "node"
    node.touch(mode=0o700)
    alias = tmp_path / "node-link"
    alias.symlink_to(node)
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    monkeypatch.delenv("CODEX_NODE_BIN", raising=False)
    monkeypatch.setattr(public_test.shutil, "which", lambda name: str(alias))
    assert public_test.application_env()["CODEX_NODE_BIN"] == str(node.resolve())


def test_status_checks_external_health_before_printing_link(tmp_path, monkeypatch, capsys, public_test):
    path = tmp_path / "url.txt"
    path.write_text("https://test-link.trycloudflare.com/chat\n")
    monkeypatch.setattr(public_test, "URL", path)
    monkeypatch.setattr(public_test, "supervisor_pid", lambda: 123)

    def healthy(url, timeout):
        assert url == "https://test-link.trycloudflare.com/api/health"
        assert timeout == 8
        response = BytesIO(b'{"status":"ok"}')
        response.status = 200
        return response

    monkeypatch.setattr(public_test, "urlopen", healthy)
    public_test.status()
    output = capsys.readouterr().out
    assert "https://test-link.trycloudflare.com/chat" in output
    assert "External backend health check passed." in output


@pytest.mark.parametrize("failure", [
    URLError("DNS lookup failed"),
    HTTPError("https://test-link.trycloudflare.com/api/health", 530, "Origin DNS error", {}, None),
])
def test_existing_start_rejects_expired_link(tmp_path, monkeypatch, capsys, public_test, failure):
    path = tmp_path / "url.txt"
    path.write_text("https://test-link.trycloudflare.com/chat\n")
    monkeypatch.setattr(public_test, "URL", path)
    monkeypatch.setattr(public_test, "supervisor_pid", lambda: 123)

    def unavailable(*args, **kwargs):
        raise failure

    monkeypatch.setattr(public_test, "urlopen", unavailable)
    with pytest.raises(RuntimeError, match="public link is unavailable.*stop.*start"):
        public_test.start()
    assert "https://test-link.trycloudflare.com/chat" not in capsys.readouterr().out


@pytest.mark.parametrize("body", [b"not JSON", b'{"status":"unhealthy"}', b"[]", b"null"])
def test_status_rejects_invalid_health(tmp_path, monkeypatch, capsys, public_test, body):
    path = tmp_path / "url.txt"
    path.write_text("https://test-link.trycloudflare.com/chat\n")
    monkeypatch.setattr(public_test, "URL", path)
    monkeypatch.setattr(public_test, "supervisor_pid", lambda: 123)

    def unexpected(*args, **kwargs):
        response = BytesIO(body)
        response.status = 200
        return response

    monkeypatch.setattr(public_test, "urlopen", unexpected)
    with pytest.raises(RuntimeError, match="public link is unavailable"):
        public_test.status()
    assert "External backend health check passed." not in capsys.readouterr().out


def test_stopped_status_does_not_probe_old_link(tmp_path, monkeypatch, capsys, public_test):
    path = tmp_path / "url.txt"
    path.write_text("https://old-link.trycloudflare.com/chat\n")
    monkeypatch.setattr(public_test, "URL", path)
    monkeypatch.setattr(public_test, "supervisor_pid", lambda: None)

    def unexpected_probe(*args, **kwargs):
        pytest.fail("Stopped sharing must not check a stale URL")

    monkeypatch.setattr(public_test, "urlopen", unexpected_probe)
    public_test.status()
    assert capsys.readouterr().out.strip() == "Public testing is stopped."


@pytest.mark.skipif(not CADDY.exists(), reason="Local sharing gateway is not installed")
def test_gateway_authentication_and_routing(tmp_path):
    servers = []

    def upstream(name):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps({"upstream": name, "path": self.path,
                    "authorization": self.headers.get("Authorization")}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.do_GET()

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        servers.append(server)
        Thread(target=server.serve_forever, daemon=True).start()
        return server.server_port

    backend_port, frontend_port = upstream("backend"), upstream("frontend")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        gateway_port = listener.getsockname()[1]
    config = (ROOT / "deploy/public-test.Caddyfile").read_text()
    for old, new in ((8001, backend_port), (3100, frontend_port), (3101, gateway_port)):
        config = config.replace(f":{old}", f":{new}")
    config_path = tmp_path / "Caddyfile"
    config_path.write_text(config)
    env = os.environ.copy()
    result = subprocess.run([str(CADDY), "hash-password"], input="test-researcher\n",
        text=True, capture_output=True, check=True)
    env["RESEARCHER_PASSWORD_HASH"] = result.stdout.strip()
    with (tmp_path / "caddy.log").open("w") as log:
        process = subprocess.Popen([str(CADDY), "run", "--config", str(config_path),
            "--adapter", "caddyfile"], env=env, stdout=log, stderr=log)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{gateway_port}") as client:
            for _ in range(50):
                try:
                    response = client.get("/chat")
                    break
                except httpx.ConnectError:
                    time.sleep(0.1)
            else:
                pytest.fail("Gateway did not start")
            assert response.status_code == 200
            researcher = ("researcher", "test-researcher")
            for path in ("/", "/chat", "/api/health", "/api/chat", "/api/study/session/start", "/_next/static/test.js"):
                response = client.get(path, headers={"Host": "public.example.test"})
                assert response.status_code == 200
                assert "WWW-Authenticate" not in response.headers
                assert response.json()["upstream"] == ("backend" if path.startswith("/api/") else "frontend")
                assert response.json()["authorization"] is None
                assert "noindex" in response.headers["X-Robots-Tag"]
                assert response.headers["Cache-Control"] == "no-store"
            for path in ("/api/chat", "/api/study/session/start", "/api/study/log-event",
                         "/api/study/evidence-use", "/api/study/feedback", "/api/study/session/complete"):
                response = client.post(path, json={})
                assert response.status_code == 200
                assert response.json()["upstream"] == "backend"
            response = client.get("/api/health", auth=("participant", "unused"))
            assert response.status_code == 200
            assert response.json()["authorization"] is None
            for path in ("/admin", "/admin/", "/%61dmin", "/api/admin/logs", "/api/admin/logs/export.csv",
                         "/api/admin/research/export/participants.csv", "/api/admin/research/export/timeline.csv",
                         "/api/admin/research/export/answers.csv", "/docs", "/redoc", "/openapi.json"):
                assert client.get(path).status_code == 401
                assert client.post(path, json={}).status_code == 401
                assert client.get(path, auth=("researcher", "wrong")).status_code == 401
                assert client.get(path, auth=("participant", "unused")).status_code == 401
                response = client.get(path, auth=researcher)
                assert response.status_code == 200
                assert response.json()["authorization"] is None
    finally:
        process.terminate()
        process.wait(timeout=10)
        for server in servers:
            server.shutdown()
            server.server_close()
