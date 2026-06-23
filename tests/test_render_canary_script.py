from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_canary_defaults_to_private_launch_urls() -> None:
    source = _source(".github/canary-render.sh")
    env_source = _source(".github/argus-env.sh")

    assert 'APP_URL="${ARGUS_CANARY_APP_URL:-$ARGUS_PRIVATE_LAUNCH_APP_URL}"' in source
    assert 'API_URL="${ARGUS_CANARY_API_URL:-$ARGUS_PRIVATE_LAUNCH_API_URL}"' in source
    assert 'ARGUS_PRIVATE_LAUNCH_APP_URL="https://argus-app-suz5.onrender.com"' in env_source
    assert 'ARGUS_PRIVATE_LAUNCH_API_URL="https://argus-ohr5.onrender.com"' in env_source


def test_canary_requires_auth_inputs_without_echoing_password() -> None:
    source = _source(".github/canary-render.sh")

    assert "ARGUS_CANARY_EMAIL" in source
    assert "ARGUS_CANARY_PASSWORD" in source
    assert "ARGUS_CANARY_PASSWORD or MOCK_USER_PASSWORD is required" in source
    assert "set -x" not in source
    assert 'echo "Logging in canary user: $EMAIL"' not in source


def test_canary_captures_warmup_mode_fingerprint_and_commit_evidence() -> None:
    source = _source(".github/canary-render.sh")

    assert (
        'EXPECT_MODE="${ARGUS_CANARY_EXPECT_MODE:-${ARGUS_WARMUP_EXPECT_MODE:-real-workflow}}"'
        in source
    )
    assert 'CANDIDATE_SHA="${ARGUS_CANARY_SHA:-${GITHUB_SHA:-}}"' in source
    assert 'CHECKED_OUT_SHA="$(git rev-parse HEAD 2>/dev/null || true)"' in source
    assert 'WARMUP_OUTPUT="$(.github/warmup-render.sh --expect-mode "$EXPECT_MODE")"' in source
    assert "extract_warmup_value env_fingerprint" in source
    assert "extract_warmup_value workflow_env_fingerprint" in source
    assert "extract_warmup_value workflow_env_status" in source
    assert "extract_warmup_value workflow_runtime_provider_mode" in source
    assert "extract_warmup_value workflow_runtime_proof" in source
    assert "extract_warmup_value workflow_task" in source
    assert "extract_warmup_value real_workflow_task" in source
    assert 'canary_expected_mode=$EXPECT_MODE' in source
    assert 'canary_env_fingerprint=$ENV_FINGERPRINT' in source
    assert 'canary_workflow_env_fingerprint=$WORKFLOW_ENV_FINGERPRINT' in source
    assert 'canary_workflow_env_status=$WORKFLOW_ENV_STATUS' in source
    assert (
        'canary_workflow_runtime_provider_mode=$WORKFLOW_RUNTIME_PROVIDER_MODE'
        in source
    )
    assert 'canary_workflow_runtime_proof=$WORKFLOW_RUNTIME_PROOF' in source
    assert 'canary_workflow_task=$WORKFLOW_TASK' in source
    assert 'canary_real_workflow_task=$REAL_WORKFLOW_TASK' in source
    assert 'canary_expected_sha=$CANDIDATE_SHA' in source
    assert 'canary_checked_out_sha=$CHECKED_OUT_SHA' in source
    assert "canary commit mismatch" in source


def test_canary_requires_render_deploy_shas_to_match_candidate() -> None:
    source = _source(".github/canary-render.sh")

    assert '"$SCRIPT_DIR/render-env-sync.sh" api-deploy-status' in source
    assert '"$SCRIPT_DIR/render-env-sync.sh" web-deploy-status' in source
    assert "extract_status_value" in source
    assert "API_DEPLOY_SHA" in source
    assert "WEB_DEPLOY_SHA" in source
    assert 'fail_canary "deploy_status" "api_deploy_status_failed"' in source
    assert 'fail_canary "deploy_status" "web_deploy_status_failed"' in source
    assert 'fail_canary "deploy_status" "api_deploy_sha_mismatch"' in source
    assert 'fail_canary "deploy_status" "web_deploy_sha_mismatch"' in source
    assert 'fail_canary "deploy_status" "api_deploy_not_live"' in source
    assert 'fail_canary "deploy_status" "web_deploy_not_live"' in source
    assert 'canary_api_deploy_sha=$API_DEPLOY_SHA' in source
    assert 'canary_web_deploy_sha=$WEB_DEPLOY_SHA' in source
    assert '"api_deploy_sha":' in source
    assert '"web_deploy_sha":' in source


def test_canary_asserts_reload_hydration_does_not_contradict_runtime_result() -> None:
    source = _source(".github/canary-render.sh")

    assert "assert_no_reload_contradiction" in source
    assert "reload hydration contradiction" in source
    assert "agent_runtime_failure_superseded" in source
    assert "retry_last_turn" in source
    assert 'recovery.get("retryable") is True' in source
    assert "authoritative_result_seen" in source
    assert "stale_retryable_failure_seen" in source


def test_canary_checks_reload_hydration_after_stream_failures() -> None:
    source = _source(".github/canary-render.sh")

    assert "handle_stream_failure" in source
    assert "checking reload hydration after stream failure" in source
    assert "fetch_conversation_messages" in source
    assert "assert_reload_hydration_payload false" in source
    assert 'handle_stream_failure "confirmation"' in source
    assert 'handle_stream_failure "run"' in source


def test_canary_writes_privacy_safe_release_evidence() -> None:
    source = _source(".github/canary-render.sh")

    assert 'EVIDENCE_PATH="${ARGUS_CANARY_EVIDENCE_PATH:-}"' in source
    assert "write_canary_evidence" in source
    assert "build_release_evidence_json" in source
    assert "CANARY_RELEASE_EVIDENCE_JSON" in source
    assert "privacy_safe_id_label" in source
    assert "conversation_label" in source
    assert "backtest_job_label" in source
    assert "result_label" in source
    assert "privacy" in source
    assert "no_raw_ids" in source
    assert "canary_evidence_path=" in source
    assert "ARGUS_CANARY_EVIDENCE_PATH" in source
    assert '"workflow_env_fingerprint":' in source
    assert '"workflow_env_status":' in source
    assert '"workflow_runtime_provider_mode":' in source
    assert '"workflow_runtime_proof":' in source
    assert 'FOCUSED_SYMBOL_PATH="${ARGUS_CANARY_FOCUSED_SYMBOL_PATH:-}"' in source
    assert 'CANARY_FOCUSED_SYMBOL_PATH="$FOCUSED_SYMBOL_PATH"' in source
    assert '"focused_symbol_path": os.environ["CANARY_FOCUSED_SYMBOL_PATH"] or None' in (
        source
    )


def test_canary_sanitizes_warmup_output_before_logging() -> None:
    source = _source(".github/canary-render.sh")

    assert "print_sanitized_warmup_output" in source
    assert 'printf "%s\\n" "$WARMUP_OUTPUT"' not in source
    assert "stale_job_scan_status=" in source
    assert "unresolved_jobs" in source
    assert "user_id" in source
    assert "task_run_id" in source
    assert "<redacted>" in source


def test_canary_writes_failure_evidence_for_controlled_failures() -> None:
    source = _source(".github/canary-render.sh")

    assert 'CANARY_STATUS="running"' in source
    assert 'CANARY_STATUS="failed"' in source
    assert "fail_canary" in source
    assert "CANARY_FAILURE_STAGE" in source
    assert "CANARY_FAILURE_REASON" in source
    assert '"failure_stage":' in source
    assert '"failure_reason":' in source
    assert 'fail_canary "commit" "canary_commit_mismatch"' in source
    assert 'fail_canary "warmup" "warmup_probe_failed"' in source
    assert 'fail_canary "${stream_name}_stream" "stream_transport_failed"' in source
    assert 'fail_canary "reload_hydration" "reload_hydration_contract_failed"' in source
    assert 'fail_canary "auth" "missing_canary_email"' in source
    assert 'fail_canary "auth" "missing_canary_password"' in source
    assert 'fail_canary "auth" "login_failed"' in source
    assert 'fail_canary "conversation" "conversation_create_failed"' in source
    assert "if ! write_canary_evidence; then" in source


def test_canary_can_write_manual_failed_capture_artifact() -> None:
    source = _source(".github/canary-render.sh")

    assert 'CAPTURE_PATH="${ARGUS_CANARY_CAPTURE_PATH:-}"' in source
    assert "write_canary_capture" in source
    assert "build_release_evidence_json" in source
    assert "release = json.loads(os.environ[\"CANARY_RELEASE_EVIDENCE_JSON\"])" in source
    assert "CANARY_CAPTURE_PATH" in source
    assert "launch_payload" in source
    assert "result_card" in source
    assert "explanation_context" in source
    assert "route_receipt" in source
    assert "failure" in source
    assert "no_raw_ids" in source
    assert "ARGUS_CANARY_CAPTURE_PATH" in source
    assert '"workflow_env_fingerprint": os.environ["CANARY_WORKFLOW_ENV_FINGERPRINT"]' in source
    assert '"workflow_env_status": os.environ["CANARY_WORKFLOW_ENV_STATUS"]' in source
    assert (
        '"workflow_runtime_provider_mode": '
        'os.environ["CANARY_WORKFLOW_RUNTIME_PROVIDER_MODE"]'
    ) in source
    assert (
        '"workflow_runtime_proof": os.environ["CANARY_WORKFLOW_RUNTIME_PROOF"]'
        in source
    )
    assert '"focused_symbol_path": os.environ["CANARY_FOCUSED_SYMBOL_PATH"] or None' in (
        source
    )


def test_canary_failure_capture_is_written_with_failure_evidence() -> None:
    source = _source(".github/canary-render.sh")
    fail_canary_body = source.split("fail_canary() {", maxsplit=1)[1].split(
        "\n}",
        maxsplit=1,
    )[0]

    assert "write_canary_evidence" in fail_canary_body
    assert "write_canary_capture" in fail_canary_body


def test_canary_writes_failure_evidence_for_backtest_job_poll_errors() -> None:
    source = _source(".github/canary-render.sh")

    assert 'fail_canary "backtest_job" "backtest_job_fetch_failed"' in source
    assert 'fail_canary "backtest_job" "backtest_job_parse_failed"' in source
    assert 'if ! curl -fsS \\' in source
    assert 'if ! poll_result="$(' in source


def test_canary_loads_root_env_and_accepts_local_aliases() -> None:
    source = _source(".github/canary-render.sh")

    assert 'source "$SCRIPT_DIR/argus-env.sh"' in source
    assert "argus_load_root_env >/dev/null || true" in source
    assert 'EMAIL="${ARGUS_CANARY_EMAIL:-${MOCK_USER_EMAIL:-}}"' in source
    assert 'PASSWORD="${ARGUS_CANARY_PASSWORD:-${MOCK_USER_PASSWORD:-}}"' in source
    assert (
        'SUPABASE_URL="${ARGUS_CANARY_SUPABASE_URL:-${SUPABASE_URL:-${SUPABASE_PROJECT_URL:-}}}"'
        in source
    )
    assert (
        'SUPABASE_SERVICE_ROLE_KEY="${ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_ROLE_KEY:-}}"'
        in source
    )


def test_canary_exercises_confirmation_and_run_backtest_action() -> None:
    source = _source(".github/canary-render.sh")

    assert (
        "Test an equal-weight AAPL and MSFT buy-and-hold strategy from January 1, "
        "2025 through June 5, 2026 with 10,000 dollars"
        in source
    )
    assert 'action.get("type") == "run_backtest"' in source
    assert "/api/v1/backtest-jobs" in source
    assert "conversation did not persist async backtest_job metadata" in source
    assert "backtest_run" in source
    assert "backtest_jobs" in source
    assert "route_receipts" in source
    assert "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY" in source


def test_canary_language_can_be_overridden_for_spanish_live_qa() -> None:
    source = _source(".github/canary-render.sh")

    assert 'LANGUAGE="${ARGUS_CANARY_LANGUAGE:-en}"' in source
    assert 'CANARY_LANGUAGE="$LANGUAGE"' in source
    assert '"language": os.environ["CANARY_LANGUAGE"]' in source
    assert '"language": "en"' not in source


def test_canary_fails_async_jobs_that_use_result_readout_fallback() -> None:
    source = _source(".github/canary-render.sh")

    assert 'source = payload.get("result_readout_source")' in source
    assert 'fallback_used = payload.get("result_readout_fallback_used")' in source
    assert 'source != "llm_explain_stage" or fallback_used is not False' in source
    assert "backtest job did not preserve LLM result readout voice" in source
    assert "select=id,status,result_run_id,execution_metadata" in source
    assert 'workflow_metadata = execution_metadata.get("workflow_backtest")' in source


def test_canary_requires_result_summary_route_receipt_for_completed_run() -> None:
    source = _source(".github/canary-render.sh")

    assert "task=eq.result_summary" in source
    assert "run_id=eq.${RESULT_RUN_ID}" in source
    assert "did not find canary result_summary route_receipts" in source
    assert 'result_run_id = str(job.get("result_run_id") or "").strip()' in source


def test_canary_uses_confirmation_card_run_action_payload() -> None:
    source = _source(".github/canary-render.sh")

    assert "RUN_ACTION=" in source
    assert "confirmation stream did not include run_backtest action" in source
    assert '"payload": {}' not in source
    assert 'json.loads(os.environ["RUN_ACTION"])' in source


def test_canary_asserts_focused_provider_path_symbols_when_configured() -> None:
    source = _source(".github/canary-render.sh")

    assert "assert_focused_symbol_path" in source
    assert 'if [ -z "$FOCUSED_SYMBOL_PATH" ]; then' in source
    assert 'CANARY_FOCUSED_SYMBOL_PATH="$FOCUSED_SYMBOL_PATH" \\' in source
    assert 'CANARY_RUN_ACTION="$RUN_ACTION" \\' in source
    assert 'if source_name == "run_action":' in source
    assert "collect_canonical_symbols" in source
    assert "SYMBOL_COLLECTION_KEYS" in source
    assert "import re" not in source
    assert "re.findall" not in source
    assert "focused symbol path missing expected symbols" in source
    assert "assert_focused_symbol_path run_action" in source
    assert "assert_focused_symbol_path job_response" in source


def test_canary_uses_temp_file_for_reload_messages_payload() -> None:
    source = _source(".github/canary-render.sh")

    assert 'temp_messages="$(mktemp' in source
    assert 'printf \'%s\' "$MESSAGES_JSON" > "$temp_messages"' in source
    assert 'python3 - "$temp_messages" <<' in source
    assert "pathlib.Path(sys.argv[1]).read_text" in source
    assert 'rm -f "$temp_messages"' in source
    assert 'python3 - "$MESSAGES_JSON" <<' not in source
    assert (
        'python3 - "$BACKTEST_ROWS" "$RECEIPT_ROWS" "$JOB_ROWS" '
        '"$BACKTEST_JOB_ID" "$RESULT_RUN_ID" <<' in source
    )
    assert 'python3 - <<\'PY\' "$MESSAGES_JSON"' not in source
    assert 'python3 - <<\'PY\' "$BACKTEST_ROWS" "$RECEIPT_ROWS"' not in source
