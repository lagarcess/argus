"""The text the interpretation model reads is frozen against measured evidence.

Unit tests never send a message through a model, so a prompt edit passes every
gate in CI and only surfaces in the paid live eval after the merge. PR #491
rewrote the shared prompt for a DCA change and silently broke asset extraction,
date preservation, and discovery routing in three unrelated places.

Changing this surface therefore requires re-measuring it, and this test is what
forces the scorecard to exist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.evals.measurement_eval_scorecard import (
    assert_scorecard_complete,
    measurement_fixture_identity_at_git_sha,
)
from tests.interpreter_prompt_surface import (
    FINGERPRINT_PATH,
    load_fingerprint,
    model_facing_surface,
    surface_drift,
)
from tests.release_promotion_evidence_support import assert_personal_measurement

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

_HOW_TO_UPDATE = f"""
This is the shared instruction text and response schema every interpreted turn
passes through, so a change here can move behavior far from the lane that made
it. To land one:

  1. Run the live measurement eval on the branch.
  2. Commit its scorecard under docs/reports/evidence/.
  3. Compare it against the scorecard named in {FINGERPRINT_PATH} and confirm no
     case regressed.
  4. Regenerate the fingerprint and point last_measured at the new scorecard.

If you did not intend to touch model-facing text, revert instead.
"""


@pytest.fixture(scope="module")
def fingerprint() -> dict[str, object]:
    return load_fingerprint(REPOSITORY_ROOT)


@pytest.fixture(scope="module")
def observed() -> dict[str, dict[str, object]]:
    return model_facing_surface(REPOSITORY_ROOT)


def test_model_facing_text_matches_its_measured_fingerprint(
    fingerprint: dict[str, object],
    observed: dict[str, dict[str, object]],
) -> None:
    recorded = fingerprint["surface"]
    assert isinstance(recorded, dict)

    changed, added, removed = surface_drift(recorded, observed)
    if not (changed or added or removed):
        return

    report = []
    for name in changed:
        was = recorded[name]
        now = observed[name]
        report.append(
            f"  changed  {name}  ({was['chars']} -> {now['chars']} chars, "
            f"{was['entries']} -> {now['entries']} entries)"
        )
    report.extend(f"  added    {name}" for name in added)
    report.extend(f"  removed  {name}" for name in removed)

    measured = fingerprint["last_measured"]
    assert isinstance(measured, dict)
    pytest.fail(
        "Text the interpretation model reads changed since it was last measured.\n"
        + "\n".join(report)
        + f"\n\nLast measured at {measured['commit']}: "
        + f"{measured['passed']} passed, {measured['failed']} failed.\n"
        + _HOW_TO_UPDATE
    )


def assert_scorecard_measures_the_prompt(
    document: dict[str, object], *, measured_commit: str
) -> None:
    """The evidence is a complete Personal measurement of the commit it names:
    no case skipped for budget, not another fixture set, and the Personal
    measurement cases as they were at that commit."""
    # A run the budget cut short measured nothing for the cases it skipped.
    assert_scorecard_complete(document)
    provenance = document.get("provenance", {})
    assert isinstance(provenance, dict)
    assert_personal_measurement(provenance)
    identity = measurement_fixture_identity_at_git_sha(
        candidate_sha=measured_commit, repository_root=REPOSITORY_ROOT
    )
    assert (
        provenance.get("candidate_sha") == measured_commit
    ), "the fingerprint's scorecard measured a different commit"
    assert provenance.get("fixture_sha256") == identity.sha256 and provenance.get(
        "fixture_case_ids"
    ) == list(
        identity.case_ids
    ), "the fingerprint's scorecard did not measure the Personal measurement cases"


def test_fingerprint_names_a_scorecard_that_exists(
    fingerprint: dict[str, object],
) -> None:
    """A fingerprint without its evidence is an unmeasured prompt."""

    measured = fingerprint["last_measured"]
    assert isinstance(measured, dict)

    scorecard = REPOSITORY_ROOT / str(measured["scorecard"])
    assert scorecard.is_file(), (
        f"{FINGERPRINT_PATH} points at {measured['scorecard']}, which is not "
        "committed. The fingerprint records that the prompt was measured, so "
        "the measurement has to travel with it."
    )

    document = json.loads(scorecard.read_text(encoding="utf-8"))
    assert_scorecard_measures_the_prompt(
        document, measured_commit=str(measured["commit"])
    )
    totals = document["totals"]
    assert totals["passed"] == measured["passed"]
    assert totals["failed"] == measured["failed"]


def test_the_interpreter_system_prompt_is_covered(
    observed: dict[str, dict[str, object]],
) -> None:
    """Guard the guard: the file that caused this must stay in scope."""

    interpreter = observed.get("src/argus/agent_runtime/llm_interpreter.py")
    assert interpreter is not None, (
        "The extractor no longer sees the interpreter's system prompt. Either "
        "the prompt moved, or the extraction rule stopped matching it."
    )
    assert int(str(interpreter["chars"])) > 10_000


def test_a_business_scorecard_is_never_the_prompts_evidence(
    fingerprint: dict[str, object],
) -> None:
    """Never-Violate 12 evidence is the Personal suite, whatever the set says."""

    from tests.evals.measurement_eval_scorecard import (
        BUSINESS_FIXTURE_DIR,
        measurement_fixture_identity,
    )

    measured = fingerprint["last_measured"]
    assert isinstance(measured, dict)
    commit = str(measured["commit"])
    document = json.loads(
        (REPOSITORY_ROOT / str(measured["scorecard"])).read_text(encoding="utf-8")
    )
    business = measurement_fixture_identity(BUSINESS_FIXTURE_DIR)
    provenance = {
        **document["provenance"],
        "fixture_sha256": business.sha256,
        "fixture_case_ids": list(business.case_ids),
    }

    named = {**document, "provenance": {**provenance, "fixture_set": "business"}}
    with pytest.raises(AssertionError, match="not the promotion measurement"):
        assert_scorecard_measures_the_prompt(named, measured_commit=commit)
    unnamed = {**document, "provenance": provenance}
    with pytest.raises(AssertionError, match="did not measure the Personal"):
        assert_scorecard_measures_the_prompt(unnamed, measured_commit=commit)
