from __future__ import annotations

import base64
import json
import os
import stat
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

from faker import Faker

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _job_body(workflow: str, job_name: str, next_job_name: str | None) -> str:
    body = workflow.split(f"  {job_name}:\n", 1)[1]
    if next_job_name is not None:
        body = body.split(f"  {next_job_name}:\n", 1)[0]
    return body


def _jwt(payload: dict[str, Any]) -> str:
    def encode(value: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")

    return f"{encode({'alg': 'none', 'typ': 'JWT'})}.{encode(payload)}.test-signature"


@contextmanager
def _supabase_session_stub(
    *,
    email: str,
    user_id: str,
    session_id: str,
    metadata_role: str | None = None,
    metadata_source: str = "private-alpha-canary",
    listed_user: bool = True,
    allowlist_role: str = "user",
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    calls: list[dict[str, Any]] = []
    access_token = _jwt(
        {
            "sub": user_id,
            "role": "authenticated",
            "session_id": session_id,
            "exp": 4_102_444_800,
        }
    )
    refresh_token = "test-refresh-token"
    app_metadata = {
        "provider": "email",
        "providers": ["email"],
        "source": metadata_source,
    }
    if metadata_role is not None:
        app_metadata["role"] = metadata_role
    user = {
        "id": user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "email": email,
        "app_metadata": app_metadata,
        "user_metadata": {},
        "identities": [],
        "created_at": "2026-08-13T00:00:00Z",
        "updated_at": "2026-08-13T00:00:00Z",
        "is_anonymous": False,
    }
    users = [user] if listed_user else []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: Any) -> None:
            return

        def _body(self) -> dict[str, Any]:
            size = int(self.headers.get("Content-Length", "0"))
            if size == 0:
                return {}
            return json.loads(self.rfile.read(size).decode("utf-8"))

        def _respond(self, payload: Any, *, status_code: int = 200) -> None:
            body = b"" if status_code == 204 else json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Total-Count", "1")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            calls.append(
                {
                    "method": "GET",
                    "path": self.path,
                    "apikey": self.headers.get("apikey"),
                }
            )
            if self.path.startswith("/rest/v1/private_alpha_allowlist?"):
                self._respond(
                    [{"email": email, "role": allowlist_role, "disabled_at": None}]
                )
                return
            if self.path.startswith("/auth/v1/admin/users?"):
                self._respond({"users": users, "aud": "authenticated"})
                return
            if self.path == "/auth/v1/user":
                self._respond({"user": user})
                return
            self._respond({"error": "not_found"}, status_code=404)

        def do_POST(self) -> None:  # noqa: N802
            body = self._body()
            calls.append(
                {
                    "method": "POST",
                    "path": self.path,
                    "body": body,
                    "apikey": self.headers.get("apikey"),
                    "authorization": self.headers.get("Authorization"),
                }
            )
            if self.path == "/auth/v1/admin/generate_link":
                self._respond(
                    {
                        **user,
                        "action_link": "https://example.test/verify",
                        "email_otp": "123456",
                        "hashed_token": "test-hashed-token",
                        "redirect_to": "",
                        "verification_type": "magiclink",
                    }
                )
                return
            if self.path == "/auth/v1/admin/users":
                users.append(user)
                self._respond(user)
                return
            if self.path.startswith("/rest/v1/private_alpha_allowlist?"):
                self._respond(
                    [{"email": email, "role": allowlist_role, "disabled_at": None}]
                )
                return
            if self.path == "/auth/v1/verify":
                self._respond(
                    {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "expires_in": 3600,
                        "expires_at": 4_102_444_800,
                        "token_type": "bearer",
                        "user": user,
                    }
                )
                return
            if self.path == "/auth/v1/logout?scope=local":
                self._respond({}, status_code=204)
                return
            self._respond({"error": "not_found"}, status_code=404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_reports_release_and_browser_surfaces_as_separate_jobs() -> None:
    workflow = _source(".github/workflows/private-alpha-canary.yml")

    release = _job_body(workflow, "release-coherence", "authenticated-browser-journey")
    browser = _job_body(workflow, "authenticated-browser-journey", None)

    assert "  canary:\n" not in workflow
    assert "continue-on-error" not in workflow
    assert "ARGUS_CANARY_SURFACE: release-coherence" in release
    assert "ARGUS_CANARY_SURFACE: authenticated-browser-journey" in browser
    assert "private-alpha-release-coherence-evidence" in release
    assert "private-alpha-authenticated-browser-evidence" in browser
    assert "Run direct API signup-denial probe" in release
    assert "Run authenticated Spanish browser journey" in browser
    assert "Run authenticated Spanish browser journey" not in release
    assert "Run direct API signup-denial probe" not in browser


def test_backend_ci_installs_the_cross_runtime_canary_test_dependency() -> None:
    workflow = _source(".github/workflows/ci.yml")
    backend = _job_body(workflow, "backend-checks", "frontend-checks")

    assert "Set up Bun for cross-runtime contract tests" in backend
    assert "Install frontend dependencies for cross-runtime contract tests" in backend
    assert "cd web && bun install --frozen-lockfile" in backend
    assert 'ARGUS_CI_BUN_VERSION: "1.3.14"' in workflow
    assert (
        backend.count("bun-version: ${{ env.ARGUS_CI_BUN_VERSION }}") == 1
    )
    assert 'bun-version: "1.3.14"' not in workflow


def test_dispatch_runs_branch_harness_against_the_resolved_deployed_sha() -> None:
    workflow = _source(".github/workflows/private-alpha-canary.yml")
    resolver = _source(".github/canary-resolve-deployed.sh")

    assert (
        "ref: ${{ github.event_name == 'schedule' && 'main' || github.sha }}" in workflow
    )
    assert "ARGUS_CANARY_SHA=$deployed_sha" in resolver
    assert "ARGUS_CANARY_HARNESS_SHA=$harness_sha" in resolver
    assert "ARGUS_CANARY_ALLOW_HARNESS_MISMATCH=$allow_harness_mismatch" in resolver
    assert 'if [ "${GITHUB_EVENT_NAME}" = "schedule" ]; then' in resolver
    assert 'git checkout --detach "$deployed_sha"' in resolver
    assert 'allow_harness_mismatch="true"' in resolver


def test_browser_journey_starts_from_private_storage_state_without_auth_forms() -> None:
    runner = _source(".github/canary-browser.sh")
    config = _source("web/playwright.config.ts")
    spec = _source("web/e2e/private-alpha-release-canary.spec.ts")
    normalized_spec = " ".join(spec.split())

    assert "ARGUS_CANARY_BROWSER_STORAGE_STATE" in runner
    assert "ARGUS_CANARY_BROWSER_STORAGE_STATE" in config
    assert "storageState:" in config
    assert "ARGUS_CANARY_BROWSER_PASSWORD" not in runner
    assert "ARGUS_CANARY_BROWSER_SIGNUP_EMAIL" not in runner
    assert 'page.goto("/?auth=signup"' not in spec
    assert 'page.goto("/?auth=login"' not in spec
    assert 'isApiResponse(response, "/auth/signup", "POST")' not in spec
    assert 'isApiResponse(response, "/auth/login", "POST")' not in spec
    assert "captcha_token" not in spec
    assert 'page.goto("/chat"' in spec
    assert "authenticated storage state" in spec
    assert 'page.getByTestId("chat-input")' in spec
    assert '"contenteditable", "true"' in normalized_spec
    assert "waitForRequest" in spec
    assert "runBacktestRequests" in spec


def test_render_runner_has_surface_specific_fail_red_entrypoints() -> None:
    source = _source(".github/canary-render.sh")

    assert 'SURFACE="${ARGUS_CANARY_SURFACE:-}"' in source
    assert "release-coherence)" in source
    assert "authenticated-browser-journey)" in source
    assert "run_release_coherence_surface" in source
    assert "run_authenticated_browser_surface" in source
    assert "validate_release_evidence_contract" in source
    browser_surface = source.split("run_authenticated_browser_surface() {", 1)[1].split(
        "\n}", 1
    )[0]
    assert "validate_browser_evidence_contract" in browser_surface
    assert "validate_release_evidence_contract" not in browser_surface
    assert "run_disabled_signup_denial_canary" in source
    assert "mint_browser_session_state" in source
    assert "revoke_browser_session" in source
    assert "browser_auth_challenge_timed_out" not in source
    assert "captcha_challenge_timeout" not in source


def test_session_state_is_private_rotated_and_absent_from_browser_environment() -> None:
    source = _source(".github/canary-render.sh")
    runner = _source(".github/canary-browser.sh")
    session_tool = _source("web/e2e/support/private-alpha-canary-session.ts")

    assert 'BROWSER_STORAGE_STATE="$(mktemp)"' in source
    assert 'BROWSER_SESSION_HANDOFF="$(mktemp)"' in source
    assert 'chmod 600 "$BROWSER_STORAGE_STATE" "$BROWSER_SESSION_HANDOFF"' in source
    assert 'rm -f "$BROWSER_STORAGE_STATE" "$BROWSER_SESSION_HANDOFF"' in source
    assert "generateLink" in session_tool
    assert "verifyOtp" in session_tool
    assert "logout?scope=local" in session_tool
    assert "private_alpha_allowlist" in session_tool
    assert 'row.role !== "user"' in session_tool
    assert 'source !== "private-alpha-canary"' in session_tool
    assert "-u SUPABASE_SERVICE_ROLE_KEY" in runner
    assert "-u ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY" in runner
    assert 'ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY="' not in runner
    assert "-u ARGUS_OPS_TOKEN" in runner
    assert "-u ARGUS_WORKFLOW_DATABASE_URL" in runner
    assert "-u RENDER_API_KEY" in runner


def test_session_tool_mints_private_storage_state_and_revokes_it(
    tmp_path: Path,
    faker: Faker,
) -> None:
    email = faker.email().lower()
    user_id = faker.uuid4()
    session_id = faker.uuid4()
    service_role_key = "test-service-role-key"
    storage_path = tmp_path / "storage-state.json"
    handoff_path = tmp_path / "session-handoff.json"

    with _supabase_session_stub(
        email=email,
        user_id=user_id,
        session_id=session_id,
    ) as (supabase_url, calls):
        env = os.environ.copy()
        env.update(
            {
                "ARGUS_CANARY_APP_URL": "https://app.example.test",
                "ARGUS_CANARY_EMAIL": email,
                "ARGUS_CANARY_SUPABASE_URL": supabase_url,
                "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY": service_role_key,
                "ARGUS_CANARY_BROWSER_STORAGE_STATE": str(storage_path),
                "ARGUS_CANARY_BROWSER_SESSION_HANDOFF": str(handoff_path),
            }
        )
        minted = subprocess.run(
            ["bun", "e2e/support/private-alpha-canary-session.ts", "mint"],
            cwd=ROOT / "web",
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert minted.returncode == 0, minted.stderr
        assert minted.stdout.strip() == "canary_session_state=ready"

        storage_state = json.loads(storage_path.read_text(encoding="utf-8"))
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        assert storage_state["cookies"]
        assert all(
            cookie["domain"] == "app.example.test" for cookie in storage_state["cookies"]
        )
        assert service_role_key not in storage_path.read_text(encoding="utf-8")
        assert handoff["user_id"] == user_id
        assert handoff["email"] == email
        assert stat.S_IMODE(storage_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(handoff_path.stat().st_mode) == 0o600
        assert service_role_key not in minted.stdout + minted.stderr
        assert email not in minted.stdout + minted.stderr

        revoked = subprocess.run(
            ["bun", "e2e/support/private-alpha-canary-session.ts", "revoke"],
            cwd=ROOT / "web",
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert revoked.returncode == 0, revoked.stderr
        assert revoked.stdout.strip() == "canary_session_revocation=completed"

    assert all(call["apikey"] == service_role_key for call in calls)
    logout = next(call for call in calls if call["path"] == "/auth/v1/logout?scope=local")
    assert logout["authorization"] == f"Bearer {handoff['access_token']}"
    assert all(service_role_key not in json.dumps(call.get("body", {})) for call in calls)


def test_session_tool_revokes_a_minted_session_that_fails_least_privilege(
    tmp_path: Path,
    faker: Faker,
) -> None:
    email = faker.email().lower()
    service_role_key = "test-service-role-key"
    env = os.environ.copy()

    with _supabase_session_stub(
        email=email,
        user_id=faker.uuid4(),
        session_id=faker.uuid4(),
        metadata_role="developer",
    ) as (supabase_url, calls):
        env.update(
            {
                "ARGUS_CANARY_APP_URL": "https://app.example.test",
                "ARGUS_CANARY_EMAIL": email,
                "ARGUS_CANARY_SUPABASE_URL": supabase_url,
                "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY": service_role_key,
                "ARGUS_CANARY_BROWSER_STORAGE_STATE": str(
                    tmp_path / "storage-state.json"
                ),
                "ARGUS_CANARY_BROWSER_SESSION_HANDOFF": str(
                    tmp_path / "session-handoff.json"
                ),
            }
        )
        result = subprocess.run(
            ["bun", "e2e/support/private-alpha-canary-session.ts", "mint"],
            cwd=ROOT / "web",
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode != 0
    assert "canary_identity_is_not_least_privilege" in result.stderr
    assert service_role_key not in result.stdout + result.stderr
    assert email not in result.stdout + result.stderr
    assert any(call["path"] == "/auth/v1/logout?scope=local" for call in calls)


def test_redaction_masks_session_tokens_and_failure_creates_no_sentinel(
    tmp_path: Path,
) -> None:
    source = _source(".github/canary-render.sh")
    function_body = source.split("redact_browser_artifacts() {", 1)[1].split("\n}", 1)[0]
    python_source = function_body.split("python3 - <<'PY'", 1)[1].split("\nPY", 1)[0]
    results = tmp_path / "playwright-results" / "case"
    results.mkdir(parents=True)
    context_path = results / "error-context.md"
    context_path.write_text(
        "access-token-value refresh-token-value canary-probe-value\n",
        encoding="utf-8",
    )
    session_path = tmp_path / "session.json"
    session_path.write_text(
        '{"access_token":"access-token-value",'
        '"refresh_token":"refresh-token-value"}\n',
        encoding="utf-8",
    )
    session_path.chmod(0o600)
    storage_path = tmp_path / "storage-state.json"
    storage_path.write_text(
        '{"cookies":[{"name":"sb-test-auth-token",'
        '"value":"encoded-cookie-value"}],"origins":[]}\n',
        encoding="utf-8",
    )
    context_path.write_text(
        "access-token-value refresh-token-value encoded-cookie-value "
        "canary-probe-value\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "CANARY_REDACT_DIR": str(tmp_path / "playwright-results"),
            "CANARY_REDACT_SESSION_PATH": str(session_path),
            "CANARY_REDACT_STORAGE_STATE_PATH": str(storage_path),
            "CANARY_REDACT_PROBE_VALUE": "canary-probe-value",
            "CANARY_REDACT_SIMULATE_FAILURE": "false",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", python_source],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert context_path.read_text(encoding="utf-8") == (
        "<redacted> <redacted> <redacted> <redacted>\n"
    )
    sentinel = tmp_path / "playwright-results" / ".redacted"
    assert sentinel.is_file()
    assert stat.S_IMODE(context_path.stat().st_mode) == 0o600

    sentinel.unlink()
    context_path.write_text("canary-probe-value\n", encoding="utf-8")
    env["CANARY_REDACT_SIMULATE_FAILURE"] = "true"
    failed = subprocess.run(
        [sys.executable, "-c", python_source],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert failed.returncode != 0
    assert not sentinel.exists()


def test_workflow_preserves_redaction_sentinel_gate_for_browser_upload() -> None:
    workflow = _source(".github/workflows/private-alpha-canary.yml")
    browser = _job_body(workflow, "authenticated-browser-journey", None)

    check = browser.split("Check browser canary context redaction", 1)[1]
    upload = browser.split("Upload browser canary failure context", 1)[1]
    assert "web/temp/playwright-results/.redacted" in check
    assert "browser_context_upload=skipped_unredacted" in check
    assert "if: failure() && steps.browser_context.outputs.ready == 'true'" in upload


def test_manual_identity_provisioning_is_safe_and_never_runs_on_schedule() -> None:
    workflow = _source(".github/workflows/private-alpha-canary.yml")
    session_tool = _source("web/e2e/support/private-alpha-canary-session.ts")
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")

    assert "canary_identity_action:" in workflow
    assert "Provision dedicated canary identity" in workflow
    provision_step = workflow.split("Provision dedicated canary identity", 1)[1].split(
        "\n      - name:", 1
    )[0]
    assert "github.event_name == 'workflow_dispatch'" in provision_step
    assert "inputs.canary_identity_action == 'provision'" in provision_step
    assert "private-alpha-canary-session.ts provision" in provision_step
    assert "CANARY_PROVISIONING_EMAIL" in session_tool
    assert "createUser" in session_tool
    assert 'source: "private-alpha-canary"' in session_tool
    assert 'language: "es-419"' in session_tool
    assert "canary_identity_provision=ready" in session_tool
    assert "canary_identity_action=provision" in runbook


def test_session_tool_provisions_only_a_safe_dedicated_identity(
    tmp_path: Path,
    faker: Faker,
) -> None:
    email = f"private-alpha-canary+{faker.sha256()[:32]}@get-argus.com"
    service_role_key = "test-service-role-key"
    env = os.environ.copy()

    with _supabase_session_stub(
        email=email,
        user_id=faker.uuid4(),
        session_id=faker.uuid4(),
        listed_user=False,
    ) as (supabase_url, calls):
        env.update(
            {
                "ARGUS_CANARY_EMAIL": email,
                "ARGUS_CANARY_SUPABASE_URL": supabase_url,
                "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY": service_role_key,
            }
        )
        result = subprocess.run(
            ["bun", "e2e/support/private-alpha-canary-session.ts", "provision"],
            cwd=ROOT / "web",
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "canary_identity_provision=ready"
    assert service_role_key not in result.stdout + result.stderr
    assert email not in result.stdout + result.stderr
    create = next(
        call
        for call in calls
        if call["method"] == "POST" and call["path"] == "/auth/v1/admin/users"
    )
    assert create["body"]["email_confirm"] is True
    assert create["body"]["app_metadata"] == {"source": "private-alpha-canary"}
    assert create["body"]["user_metadata"] == {"language": "es-419"}
    assert any(
        call["method"] == "POST"
        and call["path"].startswith("/rest/v1/private_alpha_allowlist?")
        for call in calls
    )


def test_session_tool_refuses_to_relabel_an_existing_unknown_identity(
    faker: Faker,
) -> None:
    email = f"private-alpha-canary+{faker.sha256()[:32]}@get-argus.com"
    env = os.environ.copy()

    with _supabase_session_stub(
        email=email,
        user_id=faker.uuid4(),
        session_id=faker.uuid4(),
        metadata_source="employee",
    ) as (supabase_url, calls):
        env.update(
            {
                "ARGUS_CANARY_EMAIL": email,
                "ARGUS_CANARY_SUPABASE_URL": supabase_url,
                "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
            }
        )
        result = subprocess.run(
            ["bun", "e2e/support/private-alpha-canary-session.ts", "provision"],
            cwd=ROOT / "web",
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode != 0
    assert "canary_identity_is_not_dedicated" in result.stderr
    assert email not in result.stdout + result.stderr
    assert not any(
        call["method"] == "POST"
        and call["path"].startswith("/rest/v1/private_alpha_allowlist?")
        for call in calls
    )


def test_session_tool_refuses_to_overwrite_an_elevated_allowlist_role(
    faker: Faker,
) -> None:
    email = f"private-alpha-canary+{faker.sha256()[:32]}@get-argus.com"
    env = os.environ.copy()

    with _supabase_session_stub(
        email=email,
        user_id=faker.uuid4(),
        session_id=faker.uuid4(),
        listed_user=False,
        allowlist_role="developer",
    ) as (supabase_url, calls):
        env.update(
            {
                "ARGUS_CANARY_EMAIL": email,
                "ARGUS_CANARY_SUPABASE_URL": supabase_url,
                "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
            }
        )
        result = subprocess.run(
            ["bun", "e2e/support/private-alpha-canary-session.ts", "provision"],
            cwd=ROOT / "web",
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode != 0
    assert "canary_existing_allowlist_is_not_least_privilege" in result.stderr
    assert email not in result.stdout + result.stderr
    assert not any(
        call["method"] == "POST" and call["path"] == "/auth/v1/admin/users"
        for call in calls
    )
