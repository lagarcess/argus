from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / ".github" / "private-alpha-release-profile.json"
PROFILE_UTILITY = ROOT / ".github" / "private-alpha-release-profile.py"


def _profile_utility(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PROFILE_UTILITY), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_release_profile_is_non_secret_and_defines_real_workflow_canary() -> None:
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    serialized = json.dumps(profile).lower()

    assert profile["release_mode"] == "real-workflow"
    assert profile["services"]["api"]["name"] == "argus-api"
    assert profile["services"]["web"]["name"] == "argus-app"
    assert profile["services"]["workflow"]["name"] == "argus-backtests"
    assert profile["workflow"]["real_task"] == "argus-backtests/run_backtest_job"
    assert profile["locales"]["supported"] == ["en", "es-419"]
    assert "chat.history.pinned" in profile["locales"]["required_static_keys"]
    assert profile["capabilities"]["omnisearch"] is True
    assert profile["canary"]["language"] == "es-419"
    assert "AAPL" in profile["canary"]["prompt"]
    assert profile["canary"]["search_query"] == "AAPL"
    assert profile["canary"]["decision_note"]
    assert "signup_login" in profile["canary"]["required_steps"]
    assert "browser_owned_golden_path" in profile["canary"]["required_steps"]
    assert "private_identity_handoff" in profile["canary"]["required_steps"]
    assert "deterministic_intercepted_recovery" in profile["canary"]["required_steps"]
    assert "candidate_sha" not in serialized
    assert "eyjhb" not in serialized
    assert "bearer " not in serialized
    assert "sk-" not in serialized


def test_profile_utility_validates_hashes_and_emits_expected_pairs() -> None:
    validate = _profile_utility("validate")
    assert validate.returncode == 0, validate.stderr
    assert validate.stdout.strip() == "profile_status=ready"

    profile_hash = _profile_utility("hash")
    assert profile_hash.returncode == 0, profile_hash.stderr
    assert re.fullmatch(r"[0-9a-f]{64}", profile_hash.stdout.strip())

    api_pairs = _profile_utility("env-pairs", "api")
    assert api_pairs.returncode == 0, api_pairs.stderr
    assert "ARGUS_PERSISTENCE_MODE=supabase" in api_pairs.stdout
    assert "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=true" in api_pairs.stdout

    workflow_pairs = _profile_utility("env-pairs", "workflow")
    assert workflow_pairs.returncode == 0, workflow_pairs.stderr
    assert "ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider" in workflow_pairs.stdout

    workflow_provider_mode = _profile_utility(
        "env-value", "workflow", "ARGUS_MARKET_DATA_PROVIDER_MODE"
    )
    assert workflow_provider_mode.returncode == 0, workflow_provider_mode.stderr
    assert workflow_provider_mode.stdout.strip() == "live_provider"

    allowed_keys = _profile_utility("allowed-keys", "web")
    assert allowed_keys.returncode == 0, allowed_keys.stderr
    assert "NEXT_PUBLIC_POSTHOG_KEY" in allowed_keys.stdout


def test_profile_utility_resolves_required_spanish_static_key_values() -> None:
    result = _profile_utility("static-key-values", "es-419")

    assert result.returncode == 0, result.stderr
    values = json.loads(result.stdout)
    assert values["chat.history.pinned"]
    assert values["chat.result_card.add_decision"]
    assert values["chat.confirmation.actions.run_backtest"]
    assert values["chat.result_card.save_decision"]
    assert values["command_palette.search_placeholder"]


def test_profile_utility_exposes_browser_journey_inputs() -> None:
    for field in ("prompt", "decision_state", "decision_note", "search_query"):
        result = _profile_utility("canary-value", field)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip()


def test_render_blueprint_matches_the_authoritative_nonsecret_profile() -> None:
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    render_blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    render_services = {
        service["name"]: {
            entry["key"]: entry
            for entry in service.get("envVars", [])
        }
        for service in render_blueprint["services"]
    }

    for surface in ("api", "web"):
        service_profile = profile["services"][surface]
        rendered_env = render_services[service_profile["name"]]
        expected_keys = set(service_profile["env"])
        expected_keys.update(service_profile["required_present"])
        expected_keys.update(service_profile["optional"])
        assert set(rendered_env) == expected_keys

        for key, value in service_profile["env"].items():
            assert str(rendered_env[key].get("value")) == value
        for key in service_profile["required_present"]:
            assert rendered_env[key].get("sync") is False or rendered_env[key].get("value")
        for key in service_profile["optional"]:
            assert rendered_env[key].get("sync") is False
