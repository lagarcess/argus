"""Free checks for the opt-in #606 measurement tool, never model quality."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from tests.evals import result_followup_measurement as measurement


def test_default_is_offline_and_live_requires_explicit_inputs() -> None:
    args = measurement.parser().parse_args([])
    assert args.live is False
    with pytest.raises(ValueError, match="live_inputs_required"):
        measurement.validate_live_arguments(measurement.parser().parse_args(["--live"]))


def test_schedule_has_six_adjacent_baseline_candidate_pairs() -> None:
    fixtures = measurement.load_fixtures(measurement.FIXTURES)
    schedule = measurement.build_schedule(fixtures)
    assert len(schedule) == len(fixtures["cases"]) * len(measurement.LANGUAGES) * 2
    for baseline, candidate in zip(schedule[::2], schedule[1::2], strict=True):
        assert baseline["variant"] == "baseline"
        assert candidate == {**baseline, "variant": "candidate"}


def test_fixture_validation_rejects_missing_drop_dates(tmp_path: Path) -> None:
    fixtures = measurement.load_fixtures(measurement.FIXTURES)
    broken = copy.deepcopy(fixtures)
    dca = next(case for case in broken["cases"] if case["shape"] == "dca_accumulation")
    del dca["run"]["metrics"]["aggregate"]["risk"]["max_drawdown_peak_date"]
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(broken))
    with pytest.raises(ValueError, match="dca_drop_dates_required"):
        measurement.load_fixtures(path)


def test_comparison_keeps_semantics_pending_and_detects_missing_delivery() -> None:
    good = {
        "accepted_text": "An answer",
        "sidecars": {
            "next_steps": {"items": [{"type": "question", "text": "A question?"}]}
        },
        "release_configuration": {"flag": "true"},
    }
    comparison = measurement.compare_pair(good, good)
    assert comparison["semantic_review"] == "pending_manual_review"
    assert comparison["failed_checks"] == []
    assert (
        "missing_accepted_text"
        in measurement.compare_pair(good, {**good, "accepted_text": None})[
            "failed_checks"
        ]
    )
    assert (
        "release_configuration_changed"
        in measurement.compare_pair(
            good, {**good, "release_configuration": {"flag": "false"}}
        )["failed_checks"]
    )


def test_exact_head_validation_refuses_changed_head(monkeypatch) -> None:
    monkeypatch.setattr(measurement, "git", lambda *args, **kwargs: "b" * 40)
    with pytest.raises(ValueError, match="candidate_head_changed"):
        measurement.assert_exact_head(Path.cwd(), "a" * 40)


def test_baseline_env_admission_uses_candidate_repository(monkeypatch, tmp_path) -> None:
    """The extracted baseline has no Git metadata for credential provenance."""
    from tests.evals import measurement_eval_scorecard
    from tests.evals.result_followup_measurement_probe import main

    def admit(env_file, *, repository_root):
        assert repository_root == measurement.ROOT
        raise RuntimeError("offline_admission_complete")

    monkeypatch.setattr(
        measurement_eval_scorecard, "assert_eval_env_file_untracked", admit
    )
    with pytest.raises(RuntimeError, match="offline_admission_complete"):
        main(
            {
                "live": True,
                "env_file": str(tmp_path / "measurement.env"),
                "repository_root": str(measurement.ROOT),
            }
        )


def test_offline_preview_builds_actual_composer_requests_without_provider_calls(
    monkeypatch,
) -> None:
    from tests.evals.result_followup_measurement_probe import compose_case

    # CI deliberately has no model credentials or developer model configuration.
    for key in tuple(os.environ):
        if key.endswith("_MODEL") or key.endswith("_API_KEY"):
            monkeypatch.delenv(key)
    fixtures = measurement.load_fixtures(measurement.FIXTURES)
    for case in fixtures["cases"]:
        for language in measurement.LANGUAGES:
            result = compose_case(case, language=language, live=False)
            assert result["evidence_kind"] == "offline_request_shape_only"
            assert result["semantic_review"] == "not_measured"
            assert result["provider_calls"] == 0
            assert result["accepted_text"] == case["offline_answer"][language]
            assert result["requests"]
            assert result["requests"][0]["provider"] == (
                "perplexity_agent" if case["research"] else "openrouter"
            )
            assert result["requests"][0]["payload"]
            assert result["sidecars"]["next_steps"]["items"]
            assert result["facts"]["facts"]
            if case["research"]:
                for label in ("Worst drop began", "Worst drop ended"):
                    assert result["facts"]["facts"][label]["value"] is not None
