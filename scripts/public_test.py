"""Temporary public Chat with researcher-only Admin and exports."""

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".tools" / "public-test"
ACCESS = LOCAL / "access.json"
PID = LOCAL / "supervisor.pid"
URL = LOCAL / "url.txt"
PYTHON = ROOT / "backend" / ".venv" / "bin" / "python"
CADDY = ROOT / ".tools" / "bin" / "caddy"
CLOUDFLARED = ROOT / ".tools" / "bin" / "cloudflared"


def private_write(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.chmod(path, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(text)


def supervisor_pid() -> int | None:
    if not PID.exists():
        return None
    pid = int(PID.read_text().strip())
    command = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True
    ).stdout
    return pid if f"{Path(__file__).resolve()} run" in command else None


def credentials() -> dict:
    if not ACCESS.exists():
        values = {
            "researcher": {"username": "researcher", "password": secrets.token_urlsafe(18)},
        }
        private_write(ACCESS, json.dumps(values, indent=2) + "\n")
    os.chmod(ACCESS, 0o600)
    return {"researcher": json.loads(ACCESS.read_text())["researcher"]}


def application_env() -> dict:
    env = os.environ.copy()
    env["NEXT_PUBLIC_API_BASE_URL"] = ""
    env["NEXT_BUILD_DIR"] = ".next-public"
    node = env.get("CODEX_NODE_BIN") or shutil.which("node")
    if not node:
        raise RuntimeError("Node.js was not found. Put Node on PATH or set CODEX_NODE_BIN.")
    node_path = Path(node).resolve()
    if not node_path.is_file() or not os.access(node_path, os.X_OK):
        raise RuntimeError(
            f"Node.js executable is missing or not executable: {node_path}. "
            "Set CODEX_NODE_BIN to the actual Node executable; the VS Code workspace "
            "HOME is not your macOS home directory. See docs/public_testing.md."
        )
    if node_path == (ROOT / ".tools/bin/node").resolve():
        raise RuntimeError(
            "CODEX_NODE_BIN must point to the real Node executable, not .tools/bin/node. "
            "See docs/public_testing.md."
        )
    env["CODEX_NODE_BIN"] = str(node_path)
    return env


def wait_http(url: str | Request, process: subprocess.Popen, timeout: int = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Service exited before readiness: {url}")
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"Service did not become ready: {url}")


def start() -> None:
    if supervisor_pid():
        status()
        return
    env = application_env()
    for binary in (PYTHON, CADDY, CLOUDFLARED):
        if not binary.is_file():
            raise RuntimeError(f"Missing local executable: {binary}. See docs/public_testing.md.")
    for port in (8001, 3100, 3101):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    credentials()
    print("Building a separate sharing frontend; localhost:3000 is unchanged.", flush=True)
    subprocess.run(
        [str(ROOT / ".tools" / "bin" / "pnpm"), "build"],
        cwd=ROOT / "frontend", env=env, check=True,
    )
    URL.unlink(missing_ok=True)
    with (LOCAL / "supervisor.log").open("w") as log:
        process = subprocess.Popen(
            [str(PYTHON), str(Path(__file__).resolve()), "run"],
            cwd=ROOT, env=env, stdout=log, stderr=log, start_new_session=True,
        )
    private_write(PID, str(process.pid))
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Sharing failed. See {LOCAL / 'supervisor.log'}.")
        if URL.exists():
            print("Checking the external connection before sharing the link...", flush=True)
            wait_http(urljoin(URL.read_text().strip(), "/api/health"), process, timeout=120)
            status()
            return
        time.sleep(0.5)
    process.terminate()
    raise RuntimeError(f"Tunnel readiness timed out. See {LOCAL / 'cloudflared.log'}.")


def run() -> None:
    processes = []

    def launch(name: str, command: list[str], cwd: Path, env: dict) -> subprocess.Popen:
        with (LOCAL / f"{name}.log").open("w") as log:
            process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log)
        processes.append(process)
        return process

    def interrupt(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    try:
        env = application_env()
        values = credentials()["researcher"]
        result = subprocess.run(
            [str(CADDY), "hash-password"], input=values["password"] + "\n",
            text=True, capture_output=True, check=True,
        )
        env["RESEARCHER_PASSWORD_HASH"] = result.stdout.strip()
        subprocess.run(
            [str(CADDY), "validate", "--config", str(ROOT / "deploy/public-test.Caddyfile"),
             "--adapter", "caddyfile"], env=env, check=True,
        )
        backend = launch("backend", [str(PYTHON), "-m", "uvicorn", "main:app",
            "--host", "127.0.0.1", "--port", "8001", "--no-access-log"], ROOT / "backend", env)
        wait_http("http://127.0.0.1:8001/api/health", backend)
        with urlopen("http://127.0.0.1:8001/api/admin/corpus/status", timeout=30) as response:
            corpus = json.load(response)
        if corpus.get("vectorStoreProviderActive") != "chroma" or corpus.get("fallbackUsed") is not False:
            raise RuntimeError("Chroma must be active without fallback before public testing.")
        frontend = launch("frontend", [env["CODEX_NODE_BIN"], "node_modules/next/dist/bin/next",
            "start", "--hostname", "127.0.0.1", "--port", "3100"], ROOT / "frontend", env)
        wait_http("http://127.0.0.1:3100/chat", frontend)
        gateway = launch("gateway", [str(CADDY), "run", "--config", str(ROOT / "deploy/public-test.Caddyfile"),
            "--adapter", "caddyfile"], ROOT, env)
        wait_http("http://127.0.0.1:3101/api/health", gateway)
        # Verify the private boundary before publishing a tunnel.
        for path in ("/admin", "/api/admin/logs", "/api/admin/research/export/answers.csv", "/openapi.json"):
            try:
                urlopen(f"http://127.0.0.1:3101{path}", timeout=5)
            except HTTPError as error:
                if error.code != 401:
                    raise RuntimeError("Gateway access check failed.") from error
            else:
                raise RuntimeError("Gateway unexpectedly allowed unauthorised access.")
        # Keep the Mac awake without changing system preferences.
        launch("awake", ["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())], ROOT, env)
        launch("cloudflared", [str(CLOUDFLARED), "tunnel", "--no-autoupdate", "--protocol", "http2",
            "--url", "http://127.0.0.1:3101"], ROOT, env)
        deadline = time.monotonic() + 90
        while True:
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("A sharing service stopped. Inspect .tools/public-test/*.log.")
            if not URL.exists():
                log = (LOCAL / "cloudflared.log").read_text()
                match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", log)
                if match and "Registered tunnel connection" in log:
                    private_write(URL, match.group() + "/chat\n")
                elif time.monotonic() > deadline:
                    raise RuntimeError("Cloudflare did not register a tunnel connection.")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        PID.unlink(missing_ok=True)
        URL.unlink(missing_ok=True)


def status() -> None:
    if not supervisor_pid():
        print("Public testing is stopped.")
        return
    if not URL.exists():
        print("Public testing is starting.")
        return
    public_url = URL.read_text().strip()
    try:
        with urlopen(urljoin(public_url, "/api/health"), timeout=8) as response:
            health = json.load(response)
            if response.status != 200 or not isinstance(health, dict) or health.get("status") != "ok":
                raise ValueError("Unexpected health response")
    except (OSError, ValueError) as error:
        raise RuntimeError(
            f"The sharing process is running, but its public link is unavailable: {error}. "
            "Run scripts/public_test.py stop, then scripts/public_test.py start "
            "with backend/.venv/bin/python to create a new temporary link."
        ) from error
    print(public_url)
    print("External backend health check passed.")
    print("Chat opens without a login. Admin and exports still require the researcher password.")
    print(f"Researcher password (local only, do not share): {ACCESS}")
    print("Mac and network must stay on. This is a temporary testing link, not cloud hosting.")


def stop() -> None:
    pid = supervisor_pid()
    if pid:
        os.kill(pid, signal.SIGTERM)
        for _ in range(40):
            if not supervisor_pid():
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Sharing is still stopping. Inspect supervisor.log before restarting.")
    status()


if __name__ == "__main__":
    LOCAL.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(LOCAL, 0o700)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "run", "status", "stop"])
    args = parser.parse_args()
    try:
        globals()[args.action]()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
