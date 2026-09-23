"""Free #644 gate: preserve the captured discovery replies and the em-dash rule.

These tests do not call a model. The fixture is raw evidence. Runtime owns
the writer fix and should call assert_no_em_dash on newly generated prose.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.evals.discovery_em_dash import (
    DEFAULT_FIXTURE_PATH,
    EM_DASH,
    ISSUE_644_CASE_IDS,
    DiscoveryEmDashEvidence,
    assert_no_em_dash,
    load_discovery_em_dash_evidence,
    prose_contains_em_dash,
)

EN_DASH = "\u2013"


def _cases() -> tuple[DiscoveryEmDashEvidence, ...]:
    return load_discovery_em_dash_evidence()


def test_issue_644_fixture_keeps_both_captured_replies() -> None:
    payload = json.loads(DEFAULT_FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = _cases()

    assert payload["issue"] == 644
    assert payload["verified_sha"] == "4c4e7a001150740dddef4e97fc13b99f2b0c823b"
    assert payload["environment"] == "local-live-eval"
    assert tuple(case.id for case in cases) == ISSUE_644_CASE_IDS


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case.id)
def test_issue_644_evidence_digest_matches_recorded_sha256(
    case: DiscoveryEmDashEvidence,
) -> None:
    assert case.digest() == case.sha256


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case.id)
def test_issue_644_evidence_still_contains_the_em_dash(
    case: DiscoveryEmDashEvidence,
) -> None:
    # The captured replies are the known defect. Rewriting them would hide
    # the repro. Runtime must fix generation, not this fixture.
    assert prose_contains_em_dash(case.text)
    assert case.text.count(EM_DASH) >= 1


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case.id)
def test_assert_no_em_dash_rejects_the_preserved_issue_644_replies(
    case: DiscoveryEmDashEvidence,
) -> None:
    with pytest.raises(AssertionError, match="U\\+2014"):
        assert_no_em_dash(case.text)


@pytest.mark.parametrize(
    "prose",
    [
        "Here are the confirmed options you can explore.",
        "It's built for ideas you already have, like testing a strategy.",
        "No dash here, only a hyphen-joined word.",
        f"An en dash range 2020{EN_DASH}2024 is not an em dash.",
        "",
    ],
    ids=["clean", "comma", "hyphen", "en-dash", "empty"],
)
def test_assert_no_em_dash_accepts_prose_without_u2014(prose: str) -> None:
    assert prose_contains_em_dash(prose) is False
    assert_no_em_dash(prose)


def test_loader_rejects_a_broken_fixture(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported"):
        load_discovery_em_dash_evidence(path)
