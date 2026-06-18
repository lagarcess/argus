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
    assert "ARGUS_CANARY_EVIDENCE_PATH=temp/release-evidence/canary-en.json" in runbook
    assert (
        "ARGUS_CANARY_EVIDENCE_PATH=temp/release-evidence/canary-es-419.json"
        in runbook
    )
    assert "private-alpha-canary-evidence" in runbook
    assert "Spanish readiness is a release criterion" in runbook
    assert "docs/release-manifests/TEMPLATE.md" in runbook
    assert "release manifest" in runbook
    assert "rollback target" in runbook
    assert "approver" in runbook


def test_private_alpha_release_manifest_template_has_required_audit_fields() -> None:
    template = _source("docs/release-manifests/TEMPLATE.md")

    for expected in (
        "Candidate SHA",
        "Promotion target",
        "Rollback target",
        "Approver",
        "env_fingerprint",
        "workflow_task",
        "real_workflow_task",
        "Backtest service mode",
        "Canary evidence",
        "English canary",
        "Spanish canary",
        "private-alpha-canary-evidence",
        "No raw conversation, user, run, or job ids",
    ):
        assert expected in template


def test_private_alpha_integration_doc_points_to_current_gate_and_later_memo() -> None:
    integration = _source("docs/specs/private-alpha-next-integration.md")

    assert "docs/specs/private-alpha-ci-cd-sota.md" in integration
    assert "docs/specs/private-alpha-next-decision-memo.md" in integration
    assert "later-context only" in integration
    assert "no production deploy happens from this branch" in integration.lower()
    assert "release manifest" in integration
    assert "Private Alpha Canary" in integration
    assert "local smoke" in integration
