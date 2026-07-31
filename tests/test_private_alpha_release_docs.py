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
        "ARGUS_CANARY_CAPTURE_PATH=temp/release-evidence/canary-es-419-capture.json"
        in runbook
    )
    assert "scripts/ops/canary_capture_replay.py" in runbook
    assert "Do not rerun the charged journey to collect a capture" in runbook
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


def test_public_alpha_waitlist_rollback_floor_is_durable_and_ordered() -> None:
    evidence = _source("docs/release-evidence/public-alpha-readiness.md")
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")
    evidence_text = " ".join(evidence.split())
    runbook_text = " ".join(runbook.split())

    assert "061ba50e" in evidence_text
    assert "prefer a forward fix" in evidence_text.lower()
    assert "out-of-band Render control-plane readback" in evidence_text
    assert "serviceDetails.maintenanceMode.enabled=true" in evidence_text
    assert (
        "https://argus-ohr5.onrender.com/api/v1/auth/access-requests"
        in evidence_text
    )
    assert "every configured custom API domain" in evidence_text
    assert "exact HTTP `503` maintenance-mode status" in evidence_text
    assert "configured maintenance page marker or SHA-256 fingerprint" in evidence_text
    assert "An arbitrary `403`, `429`, or `503` is not maintenance proof." in (
        evidence_text
    )
    assert "must not return HTTP `202`" not in evidence_text
    assert (
        "If the control-plane state or expected response signature cannot be "
        "verified, stop and forward-fix." in evidence_text
    )
    assert "same-SHA Render service restart" in evidence_text
    assert "restart deploy is terminal with `status=live`" in evidence_text
    assert "non-empty `finishedAt`" in evidence_text
    assert "pre-restart instance IDs" in evidence_text
    assert "old-instance shutdown/drain is complete" in evidence_text
    assert "no pre-maintenance API worker remains" in evidence_text
    assert "The table lock does not drain a worker paused before its insert." in (
        evidence_text
    )
    assert (
        "lock table public.private_alpha_allowlist in access exclusive mode;"
        in evidence_text.lower()
    )
    assert "pre-block in-flight inserts" in evidence_text
    assert "role = 'requested'" in evidence_text
    assert "disabled_at is null" in evidence_text
    assert "active_requested_rows" in evidence_text
    assert "keep maintenance enabled" in evidence_text
    assert "exact rollback SHA is live in Render deploy metadata" in evidence_text
    assert "private network, SSH, or local loopback" in evidence_text
    assert "non-mutating invalid-body probe" in evidence_text
    assert "require HTTP `404` route absence" in evidence_text
    assert "A present route, including HTTP `422`" in evidence_text
    assert "If no private verification surface is available" in evidence_text
    assert "re-read the maintenance configuration and response signature" in (
        evidence_text
    )
    assert "Disable maintenance last" in evidence_text
    assert "public invalid-body readback" in evidence_text
    assert (
        "Do not execute this SQL as part of repository verification."
        in evidence_text
    )
    for official_reference in (
        "https://render.com/docs/maintenance-mode",
        "https://render.com/docs/deploys#zero-downtime-deploys",
        "https://api-docs.render.com/reference/restart-service",
        "https://api-docs.render.com/reference/list-instances",
    ):
        assert official_reference in evidence_text

    maintenance_index = evidence_text.index(
        "out-of-band Render control-plane readback"
    )
    signature_index = evidence_text.index(
        "configured maintenance page marker or SHA-256 fingerprint"
    )
    restart_index = evidence_text.index("same-SHA Render service restart")
    restart_live_index = evidence_text.index(
        "restart deploy is terminal with `status=live`"
    )
    old_shutdown_index = evidence_text.index("old-instance shutdown/drain is complete")
    lock_index = evidence_text.lower().index(
        "lock table public.private_alpha_allowlist in access exclusive mode;"
    )
    disable_index = evidence_text.index("update public.private_alpha_allowlist")
    readback_index = evidence_text.index("select count(*) as active_requested_rows")
    commit_index = evidence_text.index("commit;")
    rollback_index = evidence_text.index("deploy the rollback")
    exact_sha_index = evidence_text.index(
        "exact rollback SHA is live in Render deploy metadata"
    )
    private_probe_index = evidence_text.index("non-mutating invalid-body probe")
    maintenance_reread_index = evidence_text.index(
        "re-read the maintenance configuration and response signature"
    )
    disable_maintenance_index = evidence_text.index("Disable maintenance last")
    public_readback_index = evidence_text.index("public invalid-body readback")
    assert (
        maintenance_index
        < signature_index
        < restart_index
        < restart_live_index
        < old_shutdown_index
        < lock_index
        < disable_index
        < readback_index
        < commit_index
        < rollback_index
        < exact_sha_index
        < private_probe_index
        < maintenance_reread_index
        < disable_maintenance_index
        < public_readback_index
    )

    assert "release-evidence/public-alpha-readiness.md" in runbook_text
    assert "061ba50e" in runbook_text
    assert "serviceDetails.maintenanceMode.enabled=true" in runbook_text
    assert "exact maintenance status and page fingerprint" in runbook_text
    assert "same-SHA restart" in runbook_text
    assert "old-instance shutdown/drain" in runbook_text
    assert "ACCESS EXCLUSIVE" in runbook_text
    assert "private invalid-body route-absence probe" in runbook_text
    assert "exact rollback SHA" in runbook_text
    assert "disable maintenance last" in runbook_text
    assert "HTTP `202`" not in runbook_text.split("### Waitlist rollback floor", 1)[1]


def test_waitlist_exposure_waits_for_paid_render_rollback_controls() -> None:
    evidence = " ".join(
        _source("docs/release-evidence/public-alpha-readiness.md").split()
    )
    runbook = " ".join(_source("docs/PRIVATE_LAUNCH_RUNBOOK.md").split())
    blueprint = _source("render.yaml")
    api_service = blueprint.split("name: argus-api", 1)[1].split("\n  - type:", 1)[0]

    assert "plan: free" in api_service
    assert (
        "The checked-in Render Blueprint still declares `argus-api` as "
        "`plan: free`." in evidence
    )
    assert (
        "Do not apply "
        "`supabase/migrations/20260731080154_add_requested_private_alpha_access.sql` "
        "and do not accept access-request traffic while `argus-api` is on "
        "Render's Free instance type." in evidence
    )
    assert (
        "Rollback below `061ba50e` is forbidden on the Free instance type"
        in evidence
    )
    assert "read back a paid API instance type from Render's control plane" in evidence
    assert "`serviceDetails.plan != free`" in evidence
    assert "prove maintenance mode is available and can be enabled" in evidence
    assert "private-network, SSH, or local-loopback verification capability" in evidence
    assert "later load-test-selected API tier change" in evidence
    assert (
        "If any paid capability is absent, stop: do not apply the migration and "
        "do not expose the route." in evidence
    )
    assert (
        "Only after every paid-control check passes may the requested-role "
        "migration be applied and access-request traffic be exposed." in evidence
    )
    for official_reference in (
        "https://render.com/docs/free",
        "https://render.com/docs/private-network",
        "https://render.com/docs/ssh",
    ):
        assert official_reference in evidence

    paid_plan_index = evidence.index(
        "read back a paid API instance type from Render's control plane"
    )
    maintenance_index = evidence.index(
        "prove maintenance mode is available and can be enabled"
    )
    private_surface_index = evidence.index(
        "private-network, SSH, or local-loopback verification capability"
    )
    exposure_index = evidence.index(
        "Only after every paid-control check passes may the requested-role migration"
    )
    assert paid_plan_index < maintenance_index < private_surface_index < exposure_index

    assert "The checked-in `argus-api` plan remains `free`" in runbook
    assert "migration and access-request exposure remain blocked" in runbook
    assert "paid API instance type" in runbook
    assert "maintenance and private/SSH/local verification controls" in runbook
    assert "later load-test-selected API tier change" in runbook
    assert "rollback below `061ba50e` is forbidden on `free`" in runbook


def test_private_launch_runbook_assigns_app_origin_and_smtp_secret_correctly() -> None:
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")
    ownership = runbook.split("## Render Environment Ownership", 1)[1].split(
        "## Runtime Tuning Flags", 1
    )[0]
    ownership_text = " ".join(ownership.split())

    assert "Both `argus-app` and `argus-api`" in ownership_text
    assert "password-recovery redirects" in ownership_text
    assert "approval signup links" in ownership_text
    assert "`ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD`" in ownership_text


def test_execution_realism_contract_is_consistent_across_canon_and_release_docs() -> None:
    for path in (
        "docs/PRODUCT.md",
        "docs/ARCHITECTURE.md",
        "docs/API_CONTRACT.md",
        "docs/PRIVATE_LAUNCH_RUNBOOK.md",
        "docs/specs/private-alpha-next-roadmap.md",
    ):
        source = " ".join(_source(path).split())

        assert "ARGUS_ENABLE_EXECUTION_REALISM" in source
        assert "active by default" in source
        assert "costs remain opt-in per idea" in source
        assert "`false|0|off|no`" in source


def test_api_contract_does_not_exclude_supported_execution_costs() -> None:
    source = " ".join(_source("docs/API_CONTRACT.md").split())

    assert "slippage, fees, order queue modeling" not in source
    assert "Modeled fees and slippage are supported when a user opts in" in source


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
    assert "Validates routing, state, full conversation-step manifests" in readme
    assert "**Live eval - only the 3 sanctioned moments:**" in readme
    assert "Pre-merge on a PR that changes runtime behavior" in readme
    assert "Main promotion candidate" in readme
    assert "After any model/provider change" in readme
    assert "**Browser QA is also real-API:**" in readme

    assert "tests/evals/README.md" in agents
    assert "mocked harness" in agents
    assert "live eval" in agents
    assert "Browser QA" in agents
