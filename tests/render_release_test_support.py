"""Shared fixtures for Render release-contract tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text()


def _render_env(service_name: str) -> dict[str, dict[str, str | bool]]:
    render_config = yaml.safe_load(_source("render.yaml"))

    for service in render_config["services"]:
        if service["name"] == service_name:
            return {env["key"]: env for env in service["envVars"]}

    raise AssertionError(f"{service_name} service missing from render.yaml")


def _render_env_payload(
    service_name: str,
    *,
    omit: set[str] | None = None,
    extra: dict[str, str] | None = None,
    overrides: dict[str, str] | None = None,
) -> str:
    omitted = omit or set()
    extra = extra or {}
    overrides = overrides or {}
    rows: list[dict[str, dict[str, str]]] = []

    for key, env in _render_env(service_name).items():
        if key in omitted:
            continue
        value = overrides.get(key)
        if value is None:
            value = str(env.get("value", ""))
            if not value and key != "NEXT_PUBLIC_POSTHOG_KEY":
                value = f"fake-secret-{key.lower()}"
        rows.append({"envVar": {"key": key, "value": value}})

    for key, value in extra.items():
        rows.append({"envVar": {"key": key, "value": value}})

    return json.dumps(rows)


def _workflow_env_payload(
    *,
    omit: set[str] | None = None,
    extra: dict[str, str] | None = None,
    overrides: dict[str, str] | None = None,
) -> str:
    omitted = omit or set()
    extra = extra or {}
    overrides = overrides or {}
    values = {
        "ARGUS_WORKFLOW_DATABASE_URL": "postgres://workflow-db.example/argus",
        "APP_ENV": "production",
        "ARGUS_RENDER_WORKFLOW_PROOF_TASK": "argus-backtests/workflow_proof",
        "ARGUS_WORKFLOW_PROOF_PLAN": "starter",
        "POETRY_VERSION": "2.1.3",
        "ARGUS_BACKTEST_WORKFLOW_TIMEOUT_SECONDS": "300",
        "ARGUS_MARKET_DATA_PROVIDER_MODE": "live_provider",
        "ENABLE_MARKET_DATA_CACHE": "false",
        "ALPACA_API_KEY": "fake-alpaca-key",
        "ALPACA_SECRET_KEY": "fake-alpaca-secret",
        "ALPACA_PAPER_TRADING": "true",
        "ARGUS_PROD_OPENROUTER_API_KEY": "fake-registered-openrouter-key",
        "ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY": "fake-guest-openrouter-key",
        "ARGUS_UTILITY_MODEL": "google/gemini-2.5-flash-lite",
        "ARGUS_UTILITY_FALLBACK_MODEL": "qwen/qwen3.5-9b",
        "ARGUS_CHAT_MODEL": "deepseek/deepseek-v4-flash",
        "ARGUS_CHAT_FALLBACK_MODEL": "qwen/qwen3.5-9b",
        "ARGUS_OPENROUTER_RESULT_SUMMARY_TIMEOUT_SECONDS": "30",
        "ARGUS_STRUCTURED_MODEL": "x-ai/grok-4.3",
        "ARGUS_STRUCTURED_FALLBACK_MODEL": "anthropic/claude-haiku-4.5",
        "ARGUS_CONTEXT_MODEL": "openai/gpt-oss-120b",
        "ARGUS_CONTEXT_FALLBACK_MODEL": "deepseek/deepseek-v4-flash",
    }
    rows: list[dict[str, dict[str, str]]] = []

    for key, default_value in values.items():
        if key in omitted:
            continue
        rows.append({"envVar": {"key": key, "value": overrides.get(key, default_value)}})

    for key, value in extra.items():
        rows.append({"envVar": {"key": key, "value": value}})

    return json.dumps(rows)


def _cron_service_payload(
    *,
    auto_deploy_trigger: str | None = None,
    runtime: str | None = None,
    schedule: str | None = None,
    build_command: str | None = None,
    start_command: str | None = None,
) -> str:
    cron = json.loads(_source(".github/private-alpha-release-profile.json"))["services"][
        "cron"
    ]
    auto_deploy_trigger = (
        cron["auto_deploy_trigger"]
        if auto_deploy_trigger is None
        else auto_deploy_trigger
    )
    runtime = cron["runtime"] if runtime is None else runtime
    schedule = cron["schedule"] if schedule is None else schedule
    build_command = cron["build_command"] if build_command is None else build_command
    start_command = cron["start_command"] if start_command is None else start_command
    return json.dumps(
        {
            "autoDeployTrigger": auto_deploy_trigger,
            "serviceDetails": {
                "runtime": runtime,
                "schedule": schedule,
                "envSpecificDetails": {
                    "buildCommand": build_command,
                    "startCommand": start_command,
                },
            },
        }
    )


def _run_render_release_audit(
    tmp_path: Path,
    *,
    api_env_json: str,
    web_env_json: str,
    workflow_env_json: str | None = None,
    cron_env_json: str | None = None,
    api_service_json: str | None = None,
    web_service_json: str | None = None,
    workflow_service_json: str | None = None,
    cron_service_json: str | None = None,
    cron_notification_json: str | None = None,
    cron_notification_lookup_fails: bool = False,
    cron_service_id: str | None = "crn-fake-maintenance",
    cron_lookup_fails: bool = False,
    expect_mode: str = "safe-off",
    isolate: bool = False,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    request_log = tmp_path / "curl-requests.log"
    fake_curl = bin_dir / "curl"
    fake_curl.write_text(
        """#!/bin/bash
printf "%s\\n" "$*" >> "$FAKE_CURL_REQUEST_LOG"
case "$*" in
  *"/services/$FAKE_API_SERVICE_ID/env-vars"*)
    printf "%s" "$FAKE_API_ENV_JSON"
    ;;
  *"/services/$FAKE_WEB_SERVICE_ID/env-vars"*)
    printf "%s" "$FAKE_WEB_ENV_JSON"
    ;;
  *"/services/$FAKE_WORKFLOW_SERVICE_ID/env-vars"*)
    printf "%s" "$FAKE_WORKFLOW_ENV_JSON"
    ;;
  *type=cron_job*)
    [ -n "$FAKE_CRON_LOOKUP_FAIL" ] && exit 22
    printf "%s" "$FAKE_CRON_LOOKUP_JSON"
    ;;
  *"/services/$FAKE_CRON_SERVICE_ID/env-vars"*)
    printf "%s" "$FAKE_CRON_ENV_JSON"
    ;;
  *"/notification-settings/overrides/services/$FAKE_CRON_SERVICE_ID"*)
    [ -n "$FAKE_CRON_NOTIFICATION_LOOKUP_FAIL" ] && exit 22
    printf "%s" "$FAKE_CRON_NOTIFICATION_JSON"
    ;;
  *"/services/$FAKE_API_SERVICE_ID"*) printf "%s" "$FAKE_API_SERVICE_JSON" ;;
  *"/services/$FAKE_WEB_SERVICE_ID"*) printf "%s" "$FAKE_WEB_SERVICE_JSON" ;;
  *"/workflows/$FAKE_WORKFLOW_SERVICE_ID"*) printf "%s" "$FAKE_WORKFLOW_SERVICE_JSON" ;;
  *"/services/$FAKE_CRON_SERVICE_ID"*) printf "%s" "$FAKE_CRON_SERVICE_JSON" ;;
  *)
    echo "unexpected curl request: $*" >&2
    exit 9
    ;;
esac
""",
    )
    fake_curl.chmod(0o755)

    cron_row = {"service": {"id": cron_service_id, "name": "argus-maintenance"}}
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "RENDER_API_KEY": "fake-render-token",
            "FAKE_API_SERVICE_ID": "srv-d78tanmuk2gs73e17nn0",
            "FAKE_WEB_SERVICE_ID": "srv-d7ap6bmslomc73eqp8m0",
            "ARGUS_RENDER_WORKFLOW_SERVICE_ID": "wfl-fake-backtests",
            "FAKE_WORKFLOW_SERVICE_ID": "wfl-fake-backtests",
            "FAKE_API_ENV_JSON": api_env_json,
            "FAKE_WEB_ENV_JSON": web_env_json,
            "FAKE_WORKFLOW_ENV_JSON": (
                _workflow_env_payload()
                if workflow_env_json is None
                else workflow_env_json
            ),
            "FAKE_CRON_SERVICE_ID": ("" if cron_service_id is None else cron_service_id),
            "FAKE_CRON_LOOKUP_JSON": json.dumps([cron_row] if cron_service_id else []),
            "FAKE_CRON_LOOKUP_FAIL": "1" if cron_lookup_fails else "",
            "FAKE_CRON_ENV_JSON": (
                _render_env_payload("argus-maintenance")
                if cron_env_json is None
                else cron_env_json
            ),
            "FAKE_API_SERVICE_JSON": (
                json.dumps({"autoDeployTrigger": "checksPass"})
                if api_service_json is None
                else api_service_json
            ),
            "FAKE_WEB_SERVICE_JSON": (
                json.dumps({"autoDeployTrigger": "checksPass"})
                if web_service_json is None
                else web_service_json
            ),
            "FAKE_WORKFLOW_SERVICE_JSON": (
                json.dumps({"autoDeployTrigger": "checksPass"})
                if workflow_service_json is None
                else workflow_service_json
            ),
            "FAKE_CRON_SERVICE_JSON": (
                _cron_service_payload()
                if cron_service_json is None
                else cron_service_json
            ),
            "FAKE_CRON_NOTIFICATION_JSON": (
                json.dumps(
                    {
                        "serviceId": cron_service_id,
                        "notificationsToSend": "failure",
                        "previewNotificationsEnabled": "default",
                    }
                )
                if cron_notification_json is None
                else cron_notification_json
            ),
            "FAKE_CRON_NOTIFICATION_LOOKUP_FAIL": (
                "1" if cron_notification_lookup_fails else ""
            ),
            "FAKE_CURL_REQUEST_LOG": str(request_log),
        }
    )

    script = ".github/render-env-sync.sh"
    cwd = str(ROOT)
    if isolate:
        # Mirror the scripts into a root with no .env so argus_load_root_env is a
        # no-op, then scrub workflow secrets from the process env. This reproduces
        # the daily-gate warmup step, which exports neither .env nor the workflow
        # secrets (ALPACA_*/segmented OpenRouter keys) it audits.
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        for name in (
            "render-env-sync.sh",
            "argus-env.sh",
            "private-alpha-release-profile.py",
            "private-alpha-release-profile.json",
        ):
            copied = github_dir / name
            shutil.copy(ROOT / ".github" / name, copied)
            copied.chmod(0o755)
        for secret in (
            "ALPACA_API_KEY",
            "ALPACA_SECRET_KEY",
            "ARGUS_PROD_OPENROUTER_API_KEY",
            "ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY",
            "OPENROUTER_API_KEY",
            "ARGUS_WORKFLOW_DATABASE_URL",
        ):
            env.pop(secret, None)
        script = str(github_dir / "render-env-sync.sh")
        cwd = str(tmp_path)

    return subprocess.run(
        [script, "release-config-audit", "--expect-mode", expect_mode],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
