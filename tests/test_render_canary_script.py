from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ops.canary_capture_replay import replay_capture

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _shell_function(source: str, name: str) -> str:
    return source.split(f"{name}() {{", 1)[1].split("\n}", 1)[0]


def _approval_validator_source(container: str, response_file: str) -> str:
    marker = f"python3 - \"${response_file}\" <<'PY'"
    return container.split(marker, 1)[1].split("\nPY", 1)[0]


def _approval_validator_result(
    validator_source: str, response_path: Path, payload: object
) -> subprocess.CompletedProcess[str]:
    response_path.write_text(json.dumps(payload), encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-c", validator_source, str(response_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_canary_defaults_to_private_launch_urls() -> None:
    source = _source(".github/canary-render.sh")
    env_source = _source(".github/argus-env.sh")

    assert 'APP_URL="${ARGUS_CANARY_APP_URL:-$ARGUS_PRIVATE_LAUNCH_APP_URL}"' in source
    assert 'API_URL="${ARGUS_CANARY_API_URL:-$ARGUS_PRIVATE_LAUNCH_API_URL}"' in source
    assert (
        'ARGUS_PRIVATE_LAUNCH_APP_URL="https://arguschat.ai"' in env_source
    )
    assert 'ARGUS_PRIVATE_LAUNCH_API_URL="https://api.arguschat.ai"' in env_source


def test_canary_requires_surface_specific_inputs_without_echoing_secrets() -> None:
    source = _source(".github/canary-render.sh")

    assert 'EMAIL="${ARGUS_CANARY_EMAIL:-${MOCK_USER_EMAIL:-}}"' in source
    assert 'PASSWORD="${ARGUS_CANARY_PASSWORD:-${MOCK_USER_PASSWORD:-}}"' in source
    assert 'SIGNUP_RUN_ID="${GITHUB_RUN_ID:-}"' in source
    assert 'SIGNUP_RUN_ATTEMPT="${GITHUB_RUN_ATTEMPT:-}"' in source
    assert 'SIGNUP_LOCAL_NONCE="${ARGUS_CANARY_LOCAL_RUN_NONCE:-}"' in source
    assert "resolve_signup_identity" in source
    assert "ARGUS_CANARY_SIGNUP_EMAIL:-" not in source
    assert "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY" in source
    assert 'fail_canary "auth" "missing_canary_email"' in source
    assert 'fail_canary "auth" "missing_canary_password"' not in source
    assert 'SURFACE="${ARGUS_CANARY_SURFACE:-}"' in source
    assert 'BROWSER_STORAGE_STATE="$(mktemp)"' in source
    assert 'BROWSER_SESSION_HANDOFF="$(mktemp)"' in source
    assert (
        'fail_canary "supabase_verifier" "missing_supabase_verifier_credentials"'
        in source
    )
    assert "set -x" not in source
    assert 'echo "$EMAIL"' not in source
    assert 'echo "$PASSWORD"' not in source


def test_canary_keeps_browser_and_service_role_secrets_out_of_curl_argv() -> None:
    source = _source(".github/canary-render.sh")

    assert 'BROWSER_AUTH_CURL_CONFIG="$(mktemp)"' in source
    assert 'SERVICE_ROLE_CURL_CONFIG="$(mktemp)"' in source
    assert 'chmod 600 "$BROWSER_AUTH_CURL_CONFIG" "$SERVICE_ROLE_CURL_CONFIG"' in source
    assert 'rm -f "$BROWSER_AUTH_CURL_CONFIG"' in source
    assert '"$SERVICE_ROLE_CURL_CONFIG"' in source
    assert '--config "$BROWSER_AUTH_CURL_CONFIG"' in source
    assert '--config "$SERVICE_ROLE_CURL_CONFIG"' in source
    assert "Authorization: Bearer ${BROWSER_ACCESS_TOKEN}" not in source
    assert "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" not in source
    assert "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" not in source
    assert '-H "Authorization: Bearer ${BROWSER_ACCESS_TOKEN}"' not in source
    assert '-H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}"' not in source
    assert '-H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}"' not in source


def test_canary_requires_exact_candidate_deploys_and_warmup_profile() -> None:
    source = _source(".github/canary-render.sh")

    assert (
        'EXPECT_MODE="${ARGUS_CANARY_EXPECT_MODE:-${ARGUS_WARMUP_EXPECT_MODE:-real-workflow}}"'
        in source
    )
    assert 'CANDIDATE_SHA="${ARGUS_CANARY_SHA:-${GITHUB_SHA:-}}"' in source
    assert 'CHECKED_OUT_SHA="$(git rev-parse HEAD 2>/dev/null || true)"' in source
    assert (
        'WARMUP_OUTPUT="$(.github/warmup-render.sh --expect-mode "$EXPECT_MODE")"'
        in source
    )
    assert '"$SCRIPT_DIR/render-env-sync.sh" api-deploy-status' in source
    assert '"$SCRIPT_DIR/render-env-sync.sh" web-deploy-status' in source
    assert '"$SCRIPT_DIR/render-env-sync.sh" workflow-version-status' in source
    assert 'fail_canary "deploy_status" "api_deploy_sha_mismatch"' in source
    assert 'fail_canary "deploy_status" "web_deploy_sha_mismatch"' in source
    assert 'fail_canary "deploy_status" "workflow_version_commit_mismatch"' in source
    assert 'fail_canary "deploy_status" "workflow_version_id_missing"' in source
    assert "workflow_commit_matches_candidate" in source
    assert 'fail_canary "release_profile" "release_profile_hash_mismatch"' in source
    assert "extract_warmup_value env_fingerprint" in source
    assert "extract_warmup_value workflow_env_fingerprint" in source
    assert "extract_warmup_value workflow_runtime_provider_mode" in source
    assert "extract_warmup_value workflow_runtime_proof" in source
    assert "canary_expected_sha=$CANDIDATE_SHA" in source
    assert "canary_checked_out_sha=$CHECKED_OUT_SHA" in source
    assert "cron-deploy-status" not in source
    assert "canary_cron_deploy" not in source


def test_canary_language_and_inputs_are_profile_owned() -> None:
    source = _source(".github/canary-render.sh")
    runner_source = _source(".github/canary-browser.sh")

    assert 'LANGUAGE="${ARGUS_CANARY_LANGUAGE:-es-419}"' in source
    assert "canary-value prompt" in source
    assert "canary-value decision_state" in source
    assert "canary-value search_query" in source
    assert 'fail_canary "release_profile" "canary_language_mismatch"' in source
    assert 'ARGUS_CANARY_BROWSER_PROMPT="$CANARY_PROMPT"' in runner_source
    assert 'ARGUS_CANARY_BROWSER_DECISION_STATE="$CANARY_DECISION_STATE"' in runner_source
    assert 'ARGUS_CANARY_BROWSER_DECISION_NOTE="$CANARY_DECISION_NOTE"' in runner_source
    assert 'ARGUS_CANARY_BROWSER_SEARCH_QUERY="$CANARY_SEARCH_QUERY"' in runner_source


def test_browser_starts_authenticated_and_preserves_the_spanish_release_gate() -> None:
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")

    assert "ARGUS_CANARY_BROWSER_USER_ID" in browser_source
    assert "openAuthenticatedChat" in browser_source
    assert 'page.goto("/chat"' in browser_source
    assert "authenticated storage state" in browser_source
    assert "storageState.cookies.some" in browser_source
    assert 'page.goto("/?auth=signup"' not in browser_source
    assert 'page.goto("/?auth=login"' not in browser_source
    assert 'isApiResponse(response, "/auth/signup", "POST")' not in browser_source
    assert 'isApiResponse(response, "/auth/login", "POST")' not in browser_source
    assert "captcha_token" not in browser_source
    assert "page.waitForURL(/\\/chat" in browser_source


def test_release_coherence_prepares_and_cleans_a_unique_signup_identity() -> None:
    shell_source = _source(".github/canary-render.sh")
    runner_source = _source(".github/canary-browser.sh")

    assert 'SIGNUP_RUN_ID="${GITHUB_RUN_ID:-}"' in shell_source
    assert 'SIGNUP_RUN_ATTEMPT="${GITHUB_RUN_ATTEMPT:-}"' in shell_source
    assert 'SIGNUP_LOCAL_NONCE="${ARGUS_CANARY_LOCAL_RUN_NONCE:-}"' in shell_source
    assert "resolve_signup_identity" in shell_source
    assert 'CANARY_REQUESTED_SIGNUP_DENIAL_EMAIL="$SIGNUP_EMAIL"' in shell_source
    assert "ARGUS_CANARY_BROWSER_SIGNUP_EMAIL" not in runner_source
    assert "SIGNUP_EMAIL" not in runner_source
    assert "signup_identity_is_safe" in shell_source
    assert "prepare_signup_identity" in shell_source
    assert "delete_signup_auth_identity" in shell_source
    assert "insert_disabled_signup_allowlist" in shell_source
    assert "cleanup_signup_identity" in shell_source
    assert "trap cleanup EXIT" in shell_source

    prepare_body = _shell_function(shell_source, "prepare_signup_identity")
    assert prepare_body.index("delete_signup_auth_identity") < prepare_body.index(
        "insert_disabled_signup_allowlist"
    )

    cleanup_body = _shell_function(shell_source, "cleanup")
    assert "cleanup_signup_identity" in cleanup_body
    assert cleanup_body.index("cleanup_signup_identity") < cleanup_body.index(
        'rm -f "$BROWSER_AUTH_CURL_CONFIG"'
    )

    delete_body = _shell_function(shell_source, "delete_signup_auth_identity")
    assert delete_body.count("collect_signup_auth_user_ids") == 2
    assert '[ ! -s "$SIGNUP_AUTH_USER_IDS" ]' in delete_body

    release_body = shell_source.split("run_release_coherence_surface() {", 1)[1].split(
        "\n}", 1
    )[0]
    assert release_body.index("signup_identity_is_safe") < release_body.index(
        "prepare_signup_identity"
    )
    assert release_body.index("prepare_signup_identity") < release_body.index(
        "run_disabled_signup_denial_canary"
    )


def test_release_coherence_denies_disabled_signup_before_welcome_approval() -> None:
    shell_source = _source(".github/canary-render.sh")
    runner_source = _source(".github/canary-browser.sh")
    release_body = shell_source.split("run_release_coherence_surface() {", 1)[1].split(
        "\n}", 1
    )[0]
    staging_body = _shell_function(shell_source, "stage_requested_signup_allowlist")
    approval_body = _shell_function(shell_source, "approve_requested_signup_allowlist")

    assert '"role": "user"' in shell_source
    assert '"disabled_at":' in shell_source
    assert "run_disabled_signup_denial_canary" in shell_source
    assert "verify_no_signup_auth_identity" in shell_source
    assert "stage_requested_signup_allowlist" in shell_source
    assert "approve_requested_signup_allowlist" in shell_source
    assert "enable_disabled_signup_allowlist" not in shell_source
    assert "-d '{\"disabled_at\":null}'" not in shell_source
    assert 'OPS_CURL_CONFIG="$(mktemp)"' in shell_source
    assert 'SIGNUP_APPROVAL_REQUEST="$(mktemp)"' in shell_source
    assert 'chmod 600 "$OPS_CURL_CONFIG"' in shell_source
    assert 'chmod 600 "$SIGNUP_APPROVAL_REQUEST"' in shell_source
    assert 'rm -f "$OPS_CURL_CONFIG"' in shell_source
    assert 'rm -f "$SIGNUP_APPROVAL_REQUEST"' in shell_source
    assert 'fail_canary "auth" "missing_ops_token"' in shell_source
    assert 'header = "Authorization: Bearer %s"' in shell_source
    assert '"$OPS_TOKEN"' in shell_source
    approval_curl_line = next(
        line.strip() for line in approval_body.splitlines() if "curl " in line
    )
    assert approval_curl_line.startswith("curl -q ")
    assert '--config "$OPS_CURL_CONFIG"' in approval_body
    assert '"${API_URL}/internal/access-requests/approve"' in approval_body
    assert 'CANARY_SIGNUP_EMAIL="$SIGNUP_EMAIL"' in approval_body
    assert ".strip().casefold()" in approval_body
    assert '--data-binary "@$SIGNUP_APPROVAL_REQUEST"' in approval_body
    assert 'set(payload) != {"approved"}' in approval_body
    assert 'payload["approved"] is not True' in approval_body
    assert "service_role_curl" not in approval_body
    assert "-X PATCH" not in approval_body
    assert '-d \'{"role":"requested","disabled_at":null}\'' in staging_body
    assert "role=eq.user" in staging_body
    assert "disabled_at=not.is.null" in staging_body
    assert "Authorization: Bearer ${ARGUS_OPS_TOKEN}" not in shell_source

    assert (
        release_body.index("prepare_signup_identity")
        < release_body.index("run_disabled_signup_denial_canary")
        < release_body.index("verify_no_signup_auth_identity")
        < release_body.index("stage_requested_signup_allowlist")
        < release_body.index("approve_requested_signup_allowlist")
    )
    assert "run_browser_canary" not in release_body

    assert "ARGUS_CANARY_BROWSER_STORAGE_STATE" in runner_source
    assert "-u SUPABASE_SERVICE_ROLE_KEY" in runner_source
    assert "-u ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY" in runner_source
    assert 'ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY="' not in runner_source
    assert "if ! env -u ARGUS_OPS_TOKEN" in shell_source
    assert "-u SUPABASE_SERVICE_ROLE_KEY" in shell_source
    assert "-u ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY" in shell_source


def test_approval_response_validators_require_exact_boolean_shape(
    tmp_path: Path,
) -> None:
    shell_source = _source(".github/canary-render.sh")
    approval_body = _shell_function(shell_source, "approve_requested_signup_allowlist")
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")
    promotion_section = runbook.split("### Requested Access Promotion", 1)[1]
    validators = (
        _approval_validator_source(
            approval_body,
            "SIGNUP_ALLOWLIST_RESPONSE",
        ),
        _approval_validator_source(promotion_section, "APPROVAL_RESPONSE"),
    )
    response_path = tmp_path / "approval-response.json"

    for validator_source in validators:
        assert (
            _approval_validator_result(
                validator_source,
                response_path,
                {"approved": True},
            ).returncode
            == 0
        )
        for invalid_payload in (
            {"approved": 1},
            {"approved": 1.0},
            {"approved": True, "unexpected": "field"},
            {"approved": False},
            {},
        ):
            assert (
                _approval_validator_result(
                    validator_source,
                    response_path,
                    invalid_payload,
                ).returncode
                != 0
            )


def test_runbook_promotion_recipe_is_fail_fast_and_subshell_scoped() -> None:
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")
    promotion_section = runbook.split("### Requested Access Promotion", 1)[1]
    recipe = promotion_section.split("```bash", 1)[1].split("```", 1)[0].strip()
    curl_line = next(line.strip() for line in recipe.splitlines() if "curl " in line)

    assert recipe.startswith("(\nset -euo pipefail\n")
    assert recipe.endswith("\n)")
    assert curl_line.startswith("curl -q ")
    assert (
        'trap \'rm -f "$OPS_CURL_CONFIG" "$APPROVAL_REQUEST" '
        '"$APPROVAL_RESPONSE"\' EXIT'
    ) in recipe
    assert 'set(payload) != {"approved"}' in recipe
    assert 'payload["approved"] is not True' in recipe


def test_runbook_generates_a_fresh_local_canary_nonce() -> None:
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")
    command = runbook.split("mkdir -p temp/release-evidence", 1)[1].split("```", 1)[0]

    assert 'ARGUS_CANARY_LOCAL_RUN_NONCE="$(poetry run python -c' in command
    assert "secrets.token_hex" in command
    assert "ARGUS_CANARY_SIGNUP_EMAIL" not in command


def test_disabled_signup_denial_probes_policy_instead_of_signup() -> None:
    shell_source = _source(".github/canary-render.sh")
    denial_body = _shell_function(shell_source, "run_disabled_signup_denial_canary")

    assert "canary-requested-signup-denial.py" in denial_body
    assert 'CANARY_REQUESTED_SIGNUP_DENIAL_API_URL="$API_URL"' in denial_body
    assert 'CANARY_REQUESTED_SIGNUP_DENIAL_EMAIL="$SIGNUP_EMAIL"' in denial_body
    assert 'CANARY_REQUESTED_SIGNUP_DENIAL_OPS_TOKEN="$OPS_TOKEN"' in denial_body
    assert "env -u ARGUS_OPS_TOKEN" in denial_body
    assert "-u SUPABASE_SERVICE_ROLE_KEY" in denial_body
    assert "-u ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY" in denial_body
    assert "run_browser_canary_phase" not in denial_body
    assert "access-denial" not in shell_source
    assert "/api/v1/auth/signup" not in _source(
        ".github/canary-requested-signup-denial.py"
    )


@pytest.mark.parametrize(
    ("run_id", "run_attempt", "local_nonce", "expected"),
    [
        ("123456", "2", "", "delivered+argus-123456-2@resend.dev"),
        ("١٢٣", "2", "", None),
        ("123", "٢", "", None),
        ("", "", "review-abc123", "delivered+argus-local-review-abc123@resend.dev"),
        ("", "", "a", None),
        ("", "", "a" * 43, None),
    ],
)
def test_canary_resolves_ci_and_local_signup_identities(
    run_id: str, run_attempt: str, local_nonce: str, expected: str | None
) -> None:
    shell_source = _source(".github/canary-render.sh")
    function_body = _shell_function(shell_source, "resolve_signup_identity")
    python_source = function_body.split("python3 - <<'PY'", 1)[1].split("\nPY", 1)[0]
    result = subprocess.run(
        [sys.executable, "-c", python_source],
        cwd=ROOT,
        env={
            **os.environ,
            "CANARY_SIGNUP_RUN_ID": run_id,
            "CANARY_SIGNUP_RUN_ATTEMPT": run_attempt,
            "CANARY_SIGNUP_LOCAL_NONCE": local_nonce,
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == (0 if expected else 1)
    assert result.stdout.strip() == (expected or "")


@pytest.mark.parametrize(
    ("run_id", "run_attempt", "local_nonce", "signup_email", "expected"),
    [
        ("123456", "2", "", "delivered+argus-123456-2@resend.dev", 0),
        ("١٢٣", "2", "", "delivered+argus-١٢٣-2@resend.dev", 1),
        ("123", "٢", "", "delivered+argus-123-٢@resend.dev", 1),
        ("", "", "review-abc123", "delivered+argus-local-review-abc123@resend.dev", 0),
        ("", "", "", "", 1),
        ("123456", "", "", "", 1),
        ("", "2", "", "", 1),
        ("123456", "2", "review-abc123", "", 1),
        ("", "", "Review", "", 1),
        ("", "", "review_1", "", 1),
        ("", "", "-review", "", 1),
        ("", "", "review-", "", 1),
        ("", "", "a", "delivered+argus-local-a@resend.dev", 1),
        ("", "", "review-1", "arbitrary@example.com", 1),
    ],
)
def test_canary_rejects_unsafe_signup_identity_modes_before_destructive_setup(
    run_id: str,
    run_attempt: str,
    local_nonce: str,
    signup_email: str,
    expected: int,
) -> None:
    shell_source = _source(".github/canary-render.sh")
    function_body = _shell_function(shell_source, "signup_identity_is_safe")
    python_source = function_body.split("python3 - <<'PY'", 1)[1].split("\nPY", 1)[0]

    def run_safety_check(
        *,
        login_email: str,
        signup_email: str,
        local_nonce: str,
    ) -> int:
        env = os.environ.copy()
        env.update(
            {
                "CANARY_LOGIN_EMAIL": login_email,
                "CANARY_SIGNUP_EMAIL": signup_email,
                "CANARY_SIGNUP_RUN_ID": run_id,
                "CANARY_SIGNUP_RUN_ATTEMPT": run_attempt,
                "CANARY_SIGNUP_LOCAL_NONCE": local_nonce,
            }
        )
        return subprocess.run(
            [sys.executable, "-c", python_source],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        ).returncode

    assert (
        run_safety_check(
            login_email="confirmed@example.com",
            signup_email=signup_email,
            local_nonce=local_nonce,
        )
        == expected
    )
    if expected == 0:
        assert (
            run_safety_check(
                login_email=signup_email,
                signup_email=signup_email,
                local_nonce=local_nonce,
            )
            == 1
        )
        assert (
            run_safety_check(
                login_email="",
                signup_email=signup_email,
                local_nonce=local_nonce,
            )
            == 0
        )
    assert (
        run_safety_check(
            login_email="confirmed@example.com",
            signup_email="arbitrary@example.com",
            local_nonce=local_nonce,
        )
        != 0
    )

    release_body = shell_source.split("run_release_coherence_surface() {", 1)[1].split(
        "\n}", 1
    )[0]
    safety_gate = release_body.index("signup_identity_is_safe")
    prepare = release_body.index("prepare_signup_identity")
    assert safety_gate < prepare
    assert "delete_signup_auth_identity" not in release_body[:safety_gate]


def test_rendered_browser_owns_the_authoritative_golden_path() -> None:
    shell_source = _source(".github/canary-render.sh")
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")

    assert "/api/v1/chat/stream" not in shell_source
    assert "save_canary_decision" not in shell_source
    assert "ARGUS_CANARY_BROWSER_PROMPT" in browser_source
    assert 'page.getByTestId("chat-input").fill(canaryPrompt)' in browser_source
    assert 'label("chat.confirmation.actions.run_backtest")' in browser_source
    assert "runBacktestRequests" in browser_source
    assert "expect(runBacktestRequests).toBe(1)" in browser_source
    assert 'label("chat.result_card.add_decision")' in browser_source
    assert 'label("chat.result_card.save_decision")' in browser_source
    assert "await page.reload()" in browser_source
    assert 'label("common.search")' in browser_source
    assert 'label("command_palette.search_placeholder")' in browser_source


def test_browser_opens_the_conversation_through_ui_and_captures_all_identities() -> None:
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")

    assert 'isApiResponse(response, "/me", "GET")' in browser_source
    assert (
        "Rendered profile hydration did not preserve Spanish identity" in browser_source
    )
    assert 'isApiResponse(response, "/conversations", "POST")' in browser_source
    assert 'searchParams.get("conversation") !== conversationId' in browser_source
    for identity in (
        "user_id",
        "conversation_id",
        "backtest_job_id",
        "backtest_run_id",
        "evidence_artifact_id",
        "decision_note_id",
        "idea_id",
        "idea_version_id",
    ):
        assert identity in browser_source
    assert (
        "Browser-captured job and run identities did not finalize together"
        in browser_source
    )
    assert (
        "Rendered decision did not preserve canonical artifact identity" in browser_source
    )
    assert "decision.note !== canaryDecisionNote" in browser_source


def test_browser_checkpoints_private_identity_for_first_run_failure_capture() -> None:
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")

    conversation_checkpoint = browser_source.index('status: "conversation_created"')
    run_click = browser_source.index('label("chat.confirmation.actions.run_backtest")')
    result_checkpoint = browser_source.index('status: "result_captured"')
    decision_click = browser_source.index('label("chat.result_card.add_decision")')
    complete_checkpoint = browser_source.index('status: "complete"')

    assert conversation_checkpoint < run_click
    assert result_checkpoint < decision_click < complete_checkpoint


def test_browser_exports_private_identity_handoff_and_shell_deletes_it() -> None:
    shell_source = _source(".github/canary-render.sh")
    runner_source = _source(".github/canary-browser.sh")
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")
    workflow = _source(".github/workflows/private-alpha-canary.yml")

    assert 'BROWSER_IDENTITY_HANDOFF="$(mktemp)"' in shell_source
    assert 'chmod 600 "$BROWSER_IDENTITY_HANDOFF"' in shell_source
    assert 'rm -f "$BROWSER_IDENTITY_HANDOFF"' in shell_source
    assert (
        'ARGUS_CANARY_BROWSER_IDENTITY_HANDOFF="$BROWSER_IDENTITY_HANDOFF"'
        in shell_source
    )
    assert "verify_browser_identity_handoff" in shell_source
    assert "stat.S_IMODE(path.stat().st_mode) & 0o077" in shell_source
    assert "ARGUS_CANARY_BROWSER_IDENTITY_HANDOFF" in runner_source
    assert "mode: 0o600" in browser_source
    assert 'source: "playwright"' in browser_source
    assert "schema_version: 1" in browser_source
    assert "access_token: accessToken" not in browser_source
    assert 'BROWSER_SESSION_HANDOFF="$(mktemp)"' in shell_source
    assert "load_browser_session" in shell_source
    assert '"access_token"' in shell_source
    assert "BROWSER_IDENTITY_HANDOFF" not in workflow


def test_shell_reuses_private_browser_session_for_read_only_api_postconditions() -> None:
    source = _source(".github/canary-render.sh")

    assert "require_browser_session_for_read_only_api_postconditions" in source
    assert "verify_api_postconditions" in source
    assert "${API_URL}/api/v1/backtest-jobs/${BACKTEST_JOB_ID}" in source
    assert "${API_URL}/api/v1/conversations/${CONVERSATION_ID}/messages" in source
    assert (
        "${API_URL}/api/v1/search?q=${encoded_search_query}&include_ledger_groups=true"
        in source
    )
    assert '--config "$BROWSER_AUTH_CURL_CONFIG"' in source
    assert '"${API_URL}/api/v1/auth/login"' not in source
    assert 'CANARY_PASSWORD="$PASSWORD"' not in source
    assert '"${API_URL}/api/v1/conversations"' not in source
    assert "/api/v1/evidence-artifacts/" not in source


def test_shell_verifies_ownership_finalization_and_exactly_one_job_and_run() -> None:
    source = _source(".github/canary-render.sh")

    assert "verify_canonical_postconditions" in source
    assert "browser-owned identity handoff" in source
    assert (
        "select=id,user_id,conversation_id,status,result_run_id,execution_metadata"
        in source
    )
    assert "select=id,user_id,conversation_id,status,conversation_result_card" in source
    assert (
        "select=id,user_id,idea_id,idea_version_id,source_conversation_id,source_run_id,artifact_type,lifecycle"
        in source
    )
    assert (
        "select=id,user_id,evidence_artifact_id,idea_id,idea_version_id,source_conversation_id,decision_state"
        in source
    )
    assert "if len(job_rows) != 1:" in source
    assert "expected exactly one canary backtest_job" in source
    assert "if len(run_rows) != 1:" in source
    assert "expected exactly one canary backtest_run" in source
    assert 'row.get("user_id") != user_id' in source
    assert 'job.get("status") != "succeeded"' in source
    assert 'run.get("status") != "completed"' in source
    assert 'evidence.get("lifecycle") != "decided"' in source
    assert (
        'decision.get("decision_state") != os.environ["CANARY_DECISION_STATE"]' in source
    )


def test_shell_requires_result_summary_receipt_and_llm_result_voice() -> None:
    source = _source(".github/canary-render.sh")

    assert "task=eq.result_summary" in source
    assert "run_id=eq.${BACKTEST_RUN_ID}" in source
    assert (
        'workflow_metadata.get("result_readout_source") != "llm_explain_stage"' in source
    )
    assert 'workflow_metadata.get("result_readout_fallback_used") is not False' in source
    assert 'row.get("task") == "result_summary"' in source


def test_shell_verifies_the_profile_owned_decision_note_text() -> None:
    source = _source(".github/canary-render.sh")

    assert "canary-value decision_note" in source
    assert "source_conversation_id,decision_state,note" in source
    assert 'CANARY_DECISION_NOTE="$DECISION_NOTE"' in source
    assert 'decision.get("note") != os.environ["CANARY_DECISION_NOTE"]' in source


def test_browser_matches_decision_state_inside_its_localized_template() -> None:
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")

    assert "function decisionStateLocator" in browser_source
    assert "exact: false" in browser_source.split(
        "function decisionStateLocator", 1
    )[1].split("\n}", 1)[0]
    assert browser_source.count("decisionStateLocator(page, canaryDecisionState)") == 2


def test_browser_proves_reload_and_omnisearch_source_identity() -> None:
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")

    assert 'import type { SearchConversationItem } from "../lib/search-contract"' in (
        browser_source
    )
    assert "function isSearchConversationItem" in browser_source
    assert "await page.reload()" in browser_source
    leave_source = browser_source.index('label("chat.new_chat")')
    open_search = browser_source.index('label("common.search")')
    click_result = browser_source.index("data-palette-row-index")
    assert leave_source < open_search < click_result
    assert "New chat did not leave the source conversation" in browser_source
    assert "Source result remained visible before Omnisearch reopening" in browser_source
    assert 'url.pathname.endsWith("/api/v1/search")' in browser_source
    assert "item.conversation_id === conversationId" in browser_source
    assert '(value as JsonRecord).type === "conversation"' in browser_source
    assert "dossier.run_id !== backtestRunId" in browser_source
    assert "action.evidence_artifact_id === evidenceArtifactId" in browser_source
    assert 'item.type === "evidence"' not in browser_source
    assert "Omnisearch did not reopen the canonical source conversation" in browser_source


def test_api_postcondition_derives_omnisearch_identity_from_conversation_dossier() -> None:
    source = _source(".github/canary-render.sh")
    postconditions = source.split("verify_api_postconditions() {", 1)[1].split(
        "\nservice_role_curl()", 1
    )[0]

    assert "from argus.api.schemas import PaginatedSearch" in postconditions
    assert "PaginatedSearch.model_validate" in postconditions
    assert 'item.type != "conversation"' in postconditions
    assert 'item.conversation_id != os.environ["CANARY_CONVERSATION_ID"]' in (
        postconditions
    )
    assert 'dossier.run_id != os.environ["CANARY_RUN_ID"]' in postconditions
    assert 'decision.state != os.environ["CANARY_DECISION_STATE"]' in postconditions
    assert 'action.evidence_artifact_id == os.environ["CANARY_EVIDENCE_ID"]' in (
        postconditions
    )
    assert 'item.get("type") == "evidence"' not in postconditions


def test_new_chat_poll_keeps_private_conversation_id_out_of_failure_output() -> None:
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")
    leave_source = browser_source.split('label("chat.new_chat")', 1)[1].split(
        'label("common.search")', 1
    )[0]

    assert '!new URL(page.url()).searchParams.has("conversation")' in leave_source
    assert 'searchParams.get("conversation")' not in leave_source
    assert ".toBe(true)" in leave_source


def test_reload_rejects_a_stale_retryable_failure_beside_the_completed_result() -> None:
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")
    reload_source = browser_source.split("await page.reload()", 1)[1]

    assert 'label("chat.error_backtest")' in reload_source
    assert 'label("common.retry")' in reload_source
    assert "toHaveCount(0" in reload_source


def test_reload_rejects_all_stale_backtest_job_cards() -> None:
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")
    reload_source = browser_source.split("await page.reload()", 1)[1].split(
        'label("chat.new_chat")', 1
    )[0]

    for label_key in (
        "chat.backtest_job.queued_title",
        "chat.backtest_job.running_title",
        "chat.backtest_job.failed_title",
    ):
        assert f'label("{label_key}")' in reload_source


def test_browser_has_separate_intercepted_typed_error_recovery_proof() -> None:
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")

    assert (
        "deterministic/intercepted recovery is not deployed backend proof"
        in browser_source
    )
    assert "page.route" in browser_source
    assert "route.fulfill" in browser_source
    assert '"Access-Control-Allow-Origin": new URL(page.url()).origin' in browser_source
    assert (
        '"authorization, content-type, idempotency-key, x-request-id"' in browser_source
    )
    conversations_mock = browser_source.split(
        'await page.route("**/api/v1/conversations"', 1
    )[1].split('await page.route("**/api/v1/chat/stream"', 1)[0]
    assert conversations_mock.index('route.request().method() === "OPTIONS"') < (
        conversations_mock.index('route.request().method() !== "POST"')
    )
    chat_mock = browser_source.split('await page.route("**/api/v1/chat/stream"', 1)[
        1
    ].split('await page.getByTestId("chat-input")', 1)[0]
    assert chat_mock.index('route.request().method() === "OPTIONS"') < (
        chat_mock.index("route.request().postDataJSON()")
    )
    assert 'type: "error"' in browser_source
    assert 'recovery_action: "retry_last_turn"' in browser_source
    assert 'label("common.retry")' in browser_source
    assert 'getByRole("status").filter({ has: retryButton })' in browser_source
    assert "expect(interceptedRunRequests).toBe(0)" in browser_source


def test_no_spend_recovery_runs_before_the_charged_golden_path() -> None:
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")

    recovery_test = browser_source.index(
        'test("deterministic/intercepted recovery is not deployed backend proof"'
    )
    charged_test = browser_source.index(
        'test("browser owns the Spanish Golden Path and exports private identities"'
    )

    assert recovery_test < charged_test


def test_browser_canary_requires_clean_console_and_no_blocking_overlay() -> None:
    browser_source = _source("web/e2e/private-alpha-release-canary.spec.ts")

    assert 'page.on("console"' in browser_source
    assert 'message.type() === "error"' in browser_source
    assert 'page.on("pageerror"' in browser_source
    assert "expect(browserErrors.consoleErrorCount).toBe(0)" in browser_source
    assert "expect(browserErrors.pageErrorCount).toBe(0)" in browser_source
    assert "blockingOverlay" in browser_source
    assert "await expect(blockingOverlay).toHaveCount(0)" in browser_source


def test_canary_writes_only_privacy_safe_human_evidence() -> None:
    source = _source(".github/canary-render.sh")

    assert 'EVIDENCE_PATH="${ARGUS_CANARY_EVIDENCE_PATH:-}"' in source
    assert 'CAPTURE_PATH="${ARGUS_CANARY_CAPTURE_PATH:-}"' in source
    assert "build_release_evidence_json" in source
    assert "write_canary_evidence" in source
    assert "write_canary_capture" in source
    assert "privacy_safe_id_label" in source
    assert '"privacy": "no_raw_ids; labels are sha256 prefixes"' in source
    assert "CANARY_RAW_IDS" in source
    assert "privacy-safe canary artifact contained a raw private identifier" in source
    assert "path.chmod(0o600)" in source
    assert (
        "CANARY_USER_ID"
        not in source.split("build_release_evidence_json() {", 1)[1].split("\n}", 1)[0]
    )


def test_canary_capture_remains_sanitized_and_replay_compatible() -> None:
    source = _source(".github/canary-render.sh")
    capture_body = source.split("write_canary_capture() {", 1)[1].split(
        "\nfail_canary() {", 1
    )[0]

    assert "scripts.ops.canary_capture_sanitizer" in capture_body
    assert "assert_sanitized_capture" in capture_body
    assert 'CANARY_MESSAGES_FILE="$API_MESSAGES_RESPONSE"' in capture_body
    assert '"launch_payload": launch_payload' in capture_body
    assert (
        '"final_response_payload": message_artifacts.get("final_response_payload")'
        in (capture_body)
    )
    assert '"route_receipt": receipt_summary(receipt_payload)' in capture_body


def test_canary_capture_builder_produces_a_replayable_artifact(tmp_path: Path) -> None:
    source = _source(".github/canary-render.sh")
    capture_body = source.split("write_canary_capture() {", 1)[1].split(
        "\nfail_canary() {", 1
    )[0]
    python_source = capture_body.split("python3 - <<'PY' || exit_code=$?", 1)[1].split(
        "\nPY", 1
    )[0]
    capture_path = tmp_path / "capture.json"
    messages_path = tmp_path / "messages.json"
    job_path = tmp_path / "job.json"
    receipts_path = tmp_path / "receipts.json"
    messages_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "role": "assistant",
                        "metadata": {
                            "final_response_payload": {
                                "result": {
                                    "total_return": 0.1284,
                                    "benchmark_return": 0.2614,
                                },
                                "explanation_context": {"benchmark_symbol": "SPY"},
                            },
                            "result_card": {
                                "title": "AAPL + MSFT",
                                "benchmark_symbol": "SPY",
                            },
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    job_path.write_text("{}", encoding="utf-8")
    receipts_path.write_text(
        json.dumps([{"task": "result_summary", "outcome": "succeeded"}]),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "CANARY_CAPTURE_PATH": str(capture_path),
            "CANARY_STATUS": "failed",
            "CANARY_FAILURE_STAGE": "browser",
            "CANARY_FAILURE_REASON": "rendered_golden_path_failed",
            "CANARY_FOCUSED_SYMBOL_PATH": "AAPL,MSFT",
            "CANARY_RELEASE_EVIDENCE_JSON": json.dumps({"language": "es-419"}),
            "CANARY_PROMPT": "Prueba AAPL y MSFT",
            "CANARY_CONVERSATION_LABEL": "conversation_abcdef123456",
            "CANARY_BACKTEST_JOB_LABEL": "backtest_job_abcdef123456",
            "CANARY_RESULT_LABEL": "backtest_run_abcdef123456",
            "CANARY_MESSAGES_FILE": str(messages_path),
            "CANARY_JOB_RESPONSE_FILE": str(job_path),
            "CANARY_RECEIPT_ROWS_FILE": str(receipts_path),
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
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    assert capture["final_response_payload"]["result"]["total_return"] == 0.1284
    assert capture["route_receipt"]["receipts"] == [
        {
            "task": "result_summary",
            "outcome": "succeeded",
            "failure_mode": None,
        }
    ]
    assert replay_capture(capture)["quick_take"]
    assert stat.S_IMODE(capture_path.stat().st_mode) == 0o600


def test_browser_failure_recovers_replay_inputs_before_writing_capture() -> None:
    source = _source(".github/canary-render.sh")
    browser_failure = source.split("if ! run_browser_canary; then", 1)[1].split(
        "\nfi", 1
    )[0]
    recovery_body = _shell_function(source, "recover_browser_failure_capture_inputs")

    assert "recover_browser_failure_capture_inputs" in browser_failure
    assert browser_failure.index("recover_browser_failure_capture_inputs") < (
        browser_failure.index('fail_canary "browser"')
    )
    assert "BROWSER_IDENTITY_HANDOFF" in recovery_body
    assert "API_MESSAGES_RESPONSE" in recovery_body
    assert "API_JOB_RESPONSE" in recovery_body
    assert "RECEIPT_ROWS" in recovery_body
    assert "backtest_jobs?select=id,result_run_id" in recovery_body
    assert "conversation_id=eq.${CONVERSATION_ID}" in recovery_body
    assert "user_id=eq.${USER_ID}" in recovery_body
    assert "route_receipts?select=task,outcome,failure_mode" in recovery_body
    assert "order=created_at.desc" in recovery_body
    assert "limit=20" in recovery_body
    receipt_query = recovery_body.split("route_receipts?", 1)[1].split('"', 1)[0]
    assert "conversation_id=eq.${CONVERSATION_ID}" in receipt_query
    assert "user_id=eq.${USER_ID}" in receipt_query
    assert "run_id" not in receipt_query
    assert "id," not in receipt_query
    receipt_probe = recovery_body.index("route_receipts?select=task,outcome,failure_mode")
    browser_session_check = recovery_body.index(
        "require_browser_session_for_read_only_api_postconditions"
    )
    assert receipt_probe < browser_session_check


def test_browser_failure_is_not_classified_as_a_captcha_failure() -> None:
    source = _source(".github/canary-render.sh")
    browser_surface = source.split("run_authenticated_browser_surface() {", 1)[1].split(
        "\n}", 1
    )[0]

    assert "browser_auth_challenge_timed_out" not in source
    assert "captcha_challenge_timeout" not in source
    assert browser_surface.index("mint_browser_session_state") < browser_surface.index(
        "run_browser_canary"
    )
    assert 'fail_canary "browser" "rendered_golden_path_failed"' in browser_surface
    assert 'tee "$BROWSER_PHASE_OUTPUT"' in source


def test_cleanup_redacts_browser_artifacts_before_the_job_uploads_them() -> None:
    source = _source(".github/canary-render.sh")
    cleanup_body = _shell_function(source, "cleanup")

    assert "redact_browser_artifacts || true" in cleanup_body
    assert cleanup_body.index("redact_browser_artifacts") < cleanup_body.index(
        'rm -f "$BROWSER_IDENTITY_HANDOFF"'
    )


def test_browser_artifact_redaction_masks_canary_credentials(tmp_path: Path) -> None:
    source = _source(".github/canary-render.sh")
    function_body = _shell_function(source, "redact_browser_artifacts")
    python_source = function_body.split("python3 - <<'PY'", 1)[1].split("\nPY", 1)[0]
    results = tmp_path / "playwright-results" / "case"
    results.mkdir(parents=True)
    context_path = results / "error-context.md"
    context_path.write_text(
        '- textbox "Contrasena": canary-password-value\n'
        '- textbox "Correo": operator@example.test\n'
        '- textbox "Correo": delivered@resend.dev\n',
        encoding="utf-8",
    )
    screenshot_path = results / "test-failed-1.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\x00")

    env = os.environ.copy()
    env.update(
        {
            "CANARY_REDACT_DIR": str(tmp_path / "playwright-results"),
            "CANARY_REDACT_PASSWORD": "canary-password-value",
            "CANARY_REDACT_EMAIL": "operator@example.test",
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
    redacted = context_path.read_text(encoding="utf-8")
    assert "canary-password-value" not in redacted
    assert "operator@example.test" not in redacted
    assert redacted.count("<redacted>") == 2
    # The Resend test recipient is non-secret and stays readable for triage.
    assert "delivered@resend.dev" in redacted
    assert not screenshot_path.exists()
    assert stat.S_IMODE(context_path.stat().st_mode) == 0o600
    assert (tmp_path / "playwright-results" / ".redacted").is_file()


def test_browser_artifact_redaction_leaves_no_marker_without_a_results_dir(
    tmp_path: Path,
) -> None:
    source = _source(".github/canary-render.sh")
    function_body = _shell_function(source, "redact_browser_artifacts")
    python_source = function_body.split("python3 - <<'PY'", 1)[1].split("\nPY", 1)[0]
    results_dir = tmp_path / "playwright-results"
    results_dir.mkdir()

    env = os.environ.copy()
    env.update(
        {
            "CANARY_REDACT_DIR": str(results_dir),
            "CANARY_REDACT_PASSWORD": "",
            "CANARY_REDACT_EMAIL": "",
        }
    )
    subprocess.run(
        [sys.executable, "-c", python_source],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert 'local results_dir="web/temp/playwright-results"' in function_body
    assert '[ -d "$results_dir" ] || return 0' in function_body
    assert (results_dir / ".redacted").is_file()


def test_failed_browser_run_is_reported_as_failed_not_not_run() -> None:
    source = _source(".github/canary-render.sh")
    runner_body = _shell_function(source, "run_browser_canary")

    assert 'BROWSER_CANARY_STATUS="failed"' in runner_body


def test_canary_writes_privacy_safe_failure_evidence() -> None:
    source = _source(".github/canary-render.sh")
    fail_body = _shell_function(source, "fail_canary")

    assert 'CANARY_STATUS="running"' in source
    assert 'CANARY_STATUS="failed"' in fail_body
    assert "CANARY_FAILURE_STAGE" in fail_body
    assert "CANARY_FAILURE_REASON" in fail_body
    assert "write_canary_evidence" in fail_body
    assert "write_canary_capture" in fail_body
    assert '"failure_stage":' in source
    assert '"failure_reason":' in source


def test_canary_requires_writable_capture_destination_before_browser_spend() -> None:
    source = _source(".github/canary-render.sh")
    preflight_body = _shell_function(source, "prepare_capture_destination")
    browser_body = source.split("run_authenticated_browser_surface() {", 1)[1].split(
        "\n}", 1
    )[0]
    release_body = source.split("run_release_coherence_surface() {", 1)[1].split(
        "\n}", 1
    )[0]

    assert 'fail_canary "capture" "missing_capture_destination"' in preflight_body
    assert 'fail_canary "capture" "capture_destination_not_writable"' in preflight_body
    assert ': > "$CAPTURE_PATH"' in preflight_body
    assert 'rm -f "$CAPTURE_PATH"' in preflight_body
    assert release_body.index("prepare_capture_destination") < release_body.index(
        "validate_release_evidence_contract"
    )
    assert browser_body.index("prepare_capture_destination") < browser_body.index(
        "run_browser_canary"
    )


def test_capture_write_failure_is_explicit_in_human_safe_evidence() -> None:
    source = _source(".github/canary-render.sh")
    fail_body = _shell_function(source, "fail_canary")

    assert 'CANARY_CAPTURE_WRITE_STATUS="failed"' in fail_body
    assert 'CANARY_CAPTURE_WRITE_FAILURE_REASON="capture_write_failed"' in fail_body
    assert "canary_capture_write_status=" in fail_body
    assert fail_body.index("write_canary_capture") < fail_body.index(
        "write_canary_evidence"
    )
    assert '"capture_write_status":' in source
    assert '"capture_write_failure_reason":' in source


def test_canary_sanitizes_warmup_output_before_logging() -> None:
    source = _source(".github/canary-render.sh")

    assert "print_sanitized_warmup_output" in source
    assert 'printf "%s\\n" "$WARMUP_OUTPUT"' not in source
    assert "stale_job_scan_status=" in source
    assert "unresolved_jobs" in source
    assert "user_id" in source
    assert "task_run_id" in source
    assert "<redacted>" in source


def test_canary_asserts_focused_provider_symbols_from_browser_job_response() -> None:
    source = _source(".github/canary-render.sh")

    assert 'FOCUSED_SYMBOL_PATH="${ARGUS_CANARY_FOCUSED_SYMBOL_PATH:-}"' in source
    assert 'CANARY_FOCUSED_SYMBOL_PATH="$FOCUSED_SYMBOL_PATH"' in source
    assert "expected_symbols" in source
    assert "actual_symbols" in source
    assert "issubset" in source
    assert "focused symbol path is incomplete" in source
    assert "re.findall" not in source


def test_workflow_runs_browser_canary_and_uploads_only_sanitized_artifacts() -> None:
    workflow = _source(".github/workflows/private-alpha-canary.yml")
    browser_job = workflow.split("  authenticated-browser-journey:\n", 1)[1]

    frontend_dependencies = browser_job.index("Install frontend dependencies")
    static_ui_assertions = browser_job.index("Run Spanish static UI canary assertions")
    local_smoke = browser_job.index("Run local predeploy smoke")
    browser_canary = browser_job.index("Run authenticated Spanish browser journey")

    assert frontend_dependencies < static_ui_assertions < local_smoke < browser_canary
    assert "Install Chromium for the authenticated browser canary" in browser_job
    assert "cd web && bun test __tests__/spanish-ui-smoke.test.ts" in workflow
    assert (
        "ARGUS_CANARY_EVIDENCE_PATH=temp/canary-evidence/authenticated-browser.json"
        in browser_job
    )
    assert (
        "ARGUS_CANARY_CAPTURE_PATH=temp/canary-evidence/authenticated-browser-capture.json"
        in browser_job
    )
    assert "temp/canary-evidence/*" not in workflow
    assert "temp/canary-evidence/authenticated-browser.json" in browser_job
    assert "temp/canary-evidence/authenticated-browser.exit" in browser_job
    assert "Upload failed authenticated-browser capture" in browser_job
    failed_capture_upload = browser_job.split(
        "Upload failed authenticated-browser capture", 1
    )[1]
    assert "if: failure()" in failed_capture_upload
    assert (
        "temp/canary-evidence/authenticated-browser-capture.json" in failed_capture_upload
    )
    assert "BROWSER_IDENTITY_HANDOFF" not in workflow


def test_successful_canary_does_not_write_replay_capture() -> None:
    source = _source(".github/canary-render.sh")
    success_body = source.split('CANARY_STATUS="passed"', 1)[1]

    assert "write_canary_evidence" in success_body
    assert "write_canary_capture" not in success_body


def test_browser_runner_is_profile_driven_and_executable() -> None:
    runner_source = _source(".github/canary-browser.sh")
    mode = (ROOT / ".github/canary-browser.sh").stat().st_mode

    assert "private-alpha-release-profile.py" in runner_source
    assert "static-key-values" in runner_source
    assert "private-alpha-release-canary.spec.ts" in runner_source
    assert "ARGUS_CANARY_BROWSER_IDENTITY_HANDOFF" in runner_source
    assert "PLAYWRIGHT_BASE_URL" in runner_source
    assert mode & stat.S_IXUSR


def test_render_canary_runner_is_executable() -> None:
    mode = (ROOT / ".github/canary-render.sh").stat().st_mode

    assert mode & stat.S_IXUSR
