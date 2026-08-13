from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "canary-deployed-sha.py"
FULL_SHA = "d67cef9" + ("a" * 33)


def _load_module():
    spec = importlib.util.spec_from_file_location("canary_deployed_sha", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _service_status(*, status: str = "live", commit: str = FULL_SHA) -> str:
    return f"status={status}\ncommit={commit}\n"


def _workflow_status(
    *, status: str = "ready", commit: str = "d67cef9", version_id: str = "wfv-current"
) -> str:
    return (
        f"workflow_version_id={version_id}\n"
        f"status={status}\n"
        f"commit={commit}\n"
    )


def _cron_status(*, status: str = "live", commit: str = FULL_SHA) -> str:
    return f"status={status}\ncommit={commit}\n"


def test_resolver_accepts_render_workflow_git_prefix() -> None:
    module = _load_module()

    assert module.resolve_deployed_sha(
        api_status=_service_status(),
        web_status=_service_status(),
        workflow_status=_workflow_status(),
        cron_status=_cron_status(),
    ) == FULL_SHA


@pytest.mark.parametrize(
    ("workflow_status", "reason"),
    [
        (_workflow_status(commit="abcdef0"), "workflow_commit_mismatch"),
        (_workflow_status(commit="not-a-sha"), "workflow_commit_mismatch"),
        (_workflow_status(version_id=""), "workflow_version_id_missing"),
    ],
)
def test_resolver_fails_closed_on_invalid_workflow_version_proof(
    workflow_status: str, reason: str
) -> None:
    module = _load_module()

    with pytest.raises(ValueError, match=reason):
        module.resolve_deployed_sha(
            api_status=_service_status(),
            web_status=_service_status(),
            workflow_status=workflow_status,
            cron_status=_cron_status(),
        )


@pytest.mark.parametrize(
    ("cron_status", "reason"),
    [
        (_cron_status(status="building"), "cron_deploy_not_live"),
        (_cron_status(commit="abcdef0"), "cron_deploy_sha_mismatch"),
        ("status=absent\ncommit=<absent>\n", "cron_deploy_not_live"),
        ("status=lookup_failed\ncommit=<unknown>\n", "cron_status_unavailable"),
    ],
)
def test_resolver_fails_closed_when_cron_is_not_live_on_the_same_release(
    cron_status: str, reason: str
) -> None:
    module = _load_module()

    with pytest.raises(ValueError, match=reason):
        module.resolve_deployed_sha(
            api_status=_service_status(),
            web_status=_service_status(),
            workflow_status=_workflow_status(),
            cron_status=cron_status,
        )
