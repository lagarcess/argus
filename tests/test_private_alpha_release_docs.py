from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_private_launch_runbook_documents_ci_cd_release_gate() -> None:
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")

    assert "docs/specs/private-alpha-ci-cd-sota.md" in runbook
    assert "docs/specs/private-alpha-next-decision-memo.md" in runbook
    assert "later-context document, not part of this release gate" in runbook
    assert ".github/local-smoke.sh --expected-sha" in runbook
    assert "ARGUS_CANARY_SHA=\"$(git rev-parse HEAD)\"" in runbook
    assert (
        "ARGUS_CANARY_EVIDENCE_PATH=temp/release-evidence/canary-es-419.json"
        in runbook
    )
    assert (
        "ARGUS_CANARY_CAPTURE_PATH=temp/release-evidence/canary-es-419-failed-capture.json"
        in runbook
    )
    assert "scripts/ops/canary_capture_replay.py" in runbook
    assert "Docker is optional" in runbook
    assert "private-alpha-canary-evidence" in runbook
    assert "authoritative Spanish release journey" in runbook
    assert "docs/release-manifests/TEMPLATE.md" in runbook
    assert "release manifest" in runbook
    assert "rollback target" in runbook
    assert "api_web_env_fingerprint" in runbook
    assert "workflow_env_fingerprint" in runbook
    assert "workflow_env_status" in runbook
    assert "workflow_runtime_provider_mode=live_provider" in runbook
    assert "workflow_runtime_proof=ready" in runbook
    assert "deployed Spanish signup/login browser" in runbook
    assert "workflow-service proof" in runbook
    assert "approver" in runbook


def test_private_alpha_release_manifest_template_has_required_audit_fields() -> None:
    template = _source("docs/release-manifests/TEMPLATE.md")

    for expected in (
        "Candidate SHA",
        "Promotion target",
        "Rollback target",
        "Approver",
        "api_web_env_fingerprint",
        "workflow_env_fingerprint",
        "workflow_env_status",
        "workflow_runtime_provider_mode",
        "workflow_runtime_proof",
        "env_fingerprint",
        "workflow_task",
        "real_workflow_task",
        "Backtest service mode",
        "Workflow service proof",
        "Secret rotation / least-privilege owner",
        "Canary evidence",
        "Failed-capture replay",
        "Authoritative Spanish release canary",
        "Release profile hash",
        "Browser signup/login proof",
        "private-alpha-canary-evidence",
        "No raw conversation, user, run, or job ids",
        "sanitized replay inputs",
    ):
        assert expected in template


def test_dated_release_manifest_distinguishes_workflow_tasks() -> None:
    manifest = _source(
        "docs/release-manifests/2026-07-14-private-alpha-release-integrity.md"
    )

    assert (
        "- Workflow proof task: `argus-backtests/workflow_proof`" in manifest
    )
    assert (
        "- Real workflow task: `argus-backtests/run_backtest_job`" in manifest
    )


def test_private_alpha_integration_doc_points_to_current_gate_and_later_memo() -> None:
    integration = _source("docs/specs/private-alpha-next-integration.md")

    assert "docs/specs/private-alpha-ci-cd-sota.md" in integration
    assert "docs/specs/private-alpha-next-decision-memo.md" in integration
    assert "later-context only" in integration
    assert "no production deploy happens from this branch" in integration.lower()
    assert "release manifest" in integration
    assert "Private Alpha Canary" in integration
    assert "local smoke" in integration
    assert "workflow_runtime_proof=ready" in integration


def test_agents_guardrail_keeps_canary_evidence_before_main_promotion() -> None:
    agents = _source("AGENTS.md")

    assert "docs/specs/private-alpha-ci-cd-sota.md" in agents
    assert "branch-deployed staging/private-alpha Render validation surface" in agents
    assert "Do not treat merge to `main` as a prerequisite for canary" in agents
    assert "`main` is the later promotion target" in agents


def test_eval_docs_document_mocked_first_test_tiers_and_agent_pointer() -> None:
    readme = _source("tests/evals/README.md")
    agents = _source("AGENTS.md")

    assert "## Test Tiers" in readme
    assert "**Mocked harness - every change (free, no API calls):**" in readme
    assert "poetry run pytest tests/evals/test_measurement_eval_harness.py" in readme
    assert "Validates routing, state, and contract logic" in readme
    assert "**Live eval - only the 3 sanctioned moments:**" in readme
    assert "Pre-merge on a PR that changes runtime behavior" in readme
    assert "Main promotion candidate" in readme
    assert "After any model/provider change" in readme
    assert "**Browser QA is also real-API:**" in readme

    assert "tests/evals/README.md" in agents
    assert "mocked harness" in agents
    assert "live eval" in agents
    assert "Browser QA" in agents
