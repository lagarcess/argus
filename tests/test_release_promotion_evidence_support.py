"""Focused tests for production-promotion evidence checks."""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

import pytest

from tests.promotion_evidence_repository import (
    REACHED_BY_THE_EVAL,
    UNREACHED_BY_THE_EVAL,
    commit_changes,
    commit_measured_repository,
    live_eval_scorecard,
    write_evidence,
)
from tests.release_promotion_evidence_support import (
    assert_main_promotion_baseline_comparison,
    assert_main_promotion_live_eval_evidence,
    assert_prose_failure_measured_on_both_sides,
)

ROOT = Path(__file__).resolve().parents[1]

# Every check that binds evidence to a build must answer the same way (#608).
evidence_identity_directions = pytest.mark.parametrize(
    ("changed", "rejection"),
    [
        pytest.param(
            UNREACHED_BY_THE_EVAL["release-flags"], None, id="release-flags-keep-it"
        ),
        pytest.param(
            (REACHED_BY_THE_EVAL["imported-module"],),
            "Measure again",
            id="imported-code-needs-a-new-measurement",
        ),
    ],
)


def _outcome(rejection: str | None) -> AbstractContextManager[object]:
    if rejection is None:
        return nullcontext()
    return pytest.raises(AssertionError, match=rejection)


def test_documented_candidate_only_failure_is_not_blocked_by_total_count(
    tmp_path: Path,
) -> None:
    baseline_sha = commit_measured_repository(tmp_path)
    candidate_sha = commit_changes(tmp_path, [REACHED_BY_THE_EVAL["imported-module"]])
    baseline_relative_path = write_evidence(
        tmp_path,
        f"baseline-{baseline_sha[:8]}.json",
        {
            "results": [
                {"id": "shared-failure", "status": "failed"},
                {"id": "candidate-only", "status": "passed"},
            ]
        },
    )
    manifest_path = tmp_path / "2026-08-21-main-production-promotion.md"
    manifest = (
        f"- Candidate SHA: `{candidate_sha}`\n"
        f"- Rollback target: `{baseline_sha}`\n"
        f"- Baseline eval scorecard: `{baseline_relative_path}`\n"
        "- `candidate-only`: model variance confirmed by an interleaved A/B.\n"
    )

    assert_main_promotion_baseline_comparison(
        manifest,
        manifest_path,
        candidate_results=[
            {"id": "shared-failure", "status": "failed"},
            {"id": "candidate-only", "status": "failed"},
        ],
        repository_root=tmp_path,
    )


@evidence_identity_directions
def test_live_eval_scorecard_stands_for_a_candidate_it_cannot_tell_apart(
    tmp_path: Path, changed: tuple[str, ...], rejection: str | None
) -> None:
    measured_sha = commit_measured_repository(tmp_path)
    candidate_sha = commit_changes(tmp_path, changed)
    scorecard = write_evidence(
        tmp_path,
        "candidate-eval-scorecard.json",
        live_eval_scorecard(tmp_path, measured_sha=measured_sha),
    )
    manifest_path = tmp_path / "2026-09-13-main-production-promotion.md"
    manifest_path.write_text(
        f"- Candidate SHA: `{candidate_sha}`\n"
        f"- Live eval scorecard: `{scorecard}`\n"
        f"- Live eval measured SHA: `{measured_sha}`\n",
        encoding="utf-8",
    )

    with _outcome(rejection):
        assert_main_promotion_live_eval_evidence(manifest_path, repository_root=tmp_path)


@evidence_identity_directions
def test_baseline_stands_for_a_deployed_build_it_cannot_tell_apart(
    tmp_path: Path, changed: tuple[str, ...], rejection: str | None
) -> None:
    measured_sha = commit_measured_repository(tmp_path)
    deployed_sha = commit_changes(tmp_path, changed)
    candidate_sha = commit_changes(
        tmp_path, [REACHED_BY_THE_EVAL["lazily-imported-module"]]
    )
    baseline = write_evidence(
        tmp_path,
        "baseline-eval-scorecard.json",
        live_eval_scorecard(tmp_path, measured_sha=measured_sha),
    )
    manifest = (
        f"- Candidate SHA: `{candidate_sha}`\n"
        f"- Rollback target: `{deployed_sha}`\n"
        f"- Baseline eval scorecard: `{baseline}`\n"
        f"- Baseline measured SHA: `{measured_sha}`\n"
    )

    with _outcome(rejection):
        assert_main_promotion_baseline_comparison(
            manifest,
            tmp_path / "2026-09-13-main-production-promotion.md",
            candidate_results=[],
            repository_root=tmp_path,
        )


@evidence_identity_directions
def test_targeted_ab_side_stands_for_a_commit_it_cannot_tell_apart(
    tmp_path: Path, changed: tuple[str, ...], rejection: str | None
) -> None:
    deployed_sha = commit_measured_repository(tmp_path)
    measured_sha = commit_changes(
        tmp_path, [REACHED_BY_THE_EVAL["lazily-imported-module"]]
    )
    candidate_sha = commit_changes(tmp_path, changed)
    sides = {
        side: write_evidence(
            tmp_path,
            f"targeted-ab-{side}.json",
            {
                "case_id": "case-a",
                "side": side,
                "provenance": {"candidate_sha": sha},
                "measurement": {"attempts": 10, "defect_count": 0},
            },
        )
        for side, sha in (("baseline", deployed_sha), ("candidate", measured_sha))
    }
    manifest = (
        f"- Targeted A/B baseline: `{sides['baseline']}`\n"
        f"- Targeted A/B candidate: `{sides['candidate']}`, measured at "
        f"`{measured_sha}`\n"
    )

    with _outcome(rejection):
        assert_prose_failure_measured_on_both_sides(
            manifest,
            tmp_path / "2026-09-13-main-production-promotion.md",
            case_id="case-a",
            deployed_sha=deployed_sha,
            candidate_sha=candidate_sha,
            repository_root=tmp_path,
        )


def test_runbook_makes_founder_browser_acceptance_the_stronger_gate() -> None:
    runbook = " ".join(
        (ROOT / "docs/PRIVATE_LAUNCH_RUNBOOK.md").read_text(encoding="utf-8").split()
    )

    assert "This eval gate is weak evidence" in runbook
    assert "Founder-overseen production browser acceptance is the stronger gate" in (
        runbook
    )
    assert "post-deploy checklist decides whether the promotion succeeded" in runbook
