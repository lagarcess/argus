from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / ".github" / "canary-requested-signup-denial.py"
SIGNUP_EMAIL = "delivered@resend.dev"


class _StubApi:
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self.payload = payload
        self.requests: list[dict[str, Any]] = []
        self.paths: list[str] = []


def _serve(stub: _StubApi) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler contract
            length = int(self.headers.get("Content-Length", "0"))
            stub.paths.append(self.path)
            stub.requests.append(json.loads(self.rfile.read(length) or b"{}"))
            body = json.dumps(stub.payload).encode("utf-8")
            self.send_response(stub.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def stub_api() -> Any:
    started: list[Any] = []

    def start(status: int, payload: dict[str, Any]) -> tuple[_StubApi, str]:
        stub = _StubApi(status, payload)
        generator = _serve(stub)
        started.append(generator)
        return stub, next(generator)

    yield start
    for generator in started:
        with pytest.raises(StopIteration):
            next(generator)


def _run_probe(api_url: str | None) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "CANARY_REQUESTED_SIGNUP_DENIAL_EMAIL": SIGNUP_EMAIL,
        "CANARY_REQUESTED_SIGNUP_DENIAL_LANGUAGE": "es-419",
    }
    if api_url is not None:
        env["CANARY_REQUESTED_SIGNUP_DENIAL_API_URL"] = api_url
    return subprocess.run(
        [sys.executable, str(PROBE)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_probe_passes_when_the_api_denies_the_requested_signup(stub_api: Any) -> None:
    stub, api_url = stub_api(400, {"code": "auth_signup_failed"})

    result = _run_probe(api_url)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "result=passed" in result.stdout
    assert stub.paths == ["/api/v1/auth/signup"]
    assert len(stub.requests) == 1
    sent = stub.requests[0]
    assert sent["email"] == SIGNUP_EMAIL
    assert sent["language"] == "es-419"
    assert sent["captcha_token"] == "argus-canary-denial-probe-unverified"
    assert len(sent["password"]) >= 32


def test_probe_never_sends_a_reusable_password(stub_api: Any) -> None:
    stub, api_url = stub_api(400, {"code": "auth_signup_failed"})

    _run_probe(api_url)
    _run_probe(api_url)

    assert stub.requests[0]["password"] != stub.requests[1]["password"]


def test_probe_fails_when_the_api_accepts_the_requested_signup(stub_api: Any) -> None:
    stub, api_url = stub_api(200, {"user": {"email": SIGNUP_EMAIL}})

    result = _run_probe(api_url)

    assert result.returncode == 1
    assert "result=unexpected_response status=200" in result.stdout
    # A live denial regression must be reported, never retried into ambiguity.
    assert len(stub.requests) == 1


def test_probe_fails_when_the_denial_code_changes(stub_api: Any) -> None:
    _, api_url = stub_api(400, {"code": "captcha_unavailable"})

    result = _run_probe(api_url)

    assert result.returncode == 1
    assert "result=unexpected_response" in result.stdout
    assert "'captcha_unavailable'" in result.stdout


def test_probe_fails_closed_without_configuration() -> None:
    result = _run_probe(None)

    assert result.returncode == 1
    assert "result=configuration_error" in result.stdout
    assert "CANARY_REQUESTED_SIGNUP_DENIAL_API_URL" in result.stdout


def test_probe_retries_transport_failures_then_fails() -> None:
    # Port 1 is reserved and refuses connections on every supported runner.
    result = _run_probe("http://127.0.0.1:1")

    assert result.returncode == 1
    assert "attempt=1 result=transport_error" in result.stdout
    assert "attempt=2 result=transport_error" in result.stdout
    assert "result=transport_failed" in result.stdout


def test_probe_keeps_the_signup_address_out_of_its_own_output(stub_api: Any) -> None:
    _, api_url = stub_api(400, {"code": "auth_signup_failed"})

    result = _run_probe(api_url)

    assert SIGNUP_EMAIL not in result.stdout
    assert SIGNUP_EMAIL not in result.stderr
