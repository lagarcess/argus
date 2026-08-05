from __future__ import annotations

import pytest

from scripts.market_data.offline_peer_selection import (
    PeerCandidate,
    PeerSelection,
    PeerSelectionContractError,
    select_peer,
)


def test_direct_competitor_beats_better_ranked_credible_peer() -> None:
    candidates = [
        PeerCandidate(
            candidate_id="peer:credible",
            relationship="credible_peer",
            retrieval_rank=1,
        ),
        PeerCandidate(
            candidate_id="peer:direct",
            relationship="direct_competitor",
            retrieval_rank=8,
        ),
    ]

    decision = select_peer(candidates)

    assert decision == PeerSelection(
        selected_candidate_id="peer:direct",
        decision="selected",
        decision_code="selected_direct_competitor",
    )


def test_credible_peer_is_selected_when_no_direct_competitor_survives() -> None:
    decision = select_peer(
        [
            PeerCandidate("peer:weak", "weak_match", 1),
            PeerCandidate("peer:credible", "credible_peer", 4),
        ]
    )

    assert decision == PeerSelection(
        selected_candidate_id="peer:credible",
        decision="selected",
        decision_code="selected_credible_peer",
    )


@pytest.mark.parametrize(
    "candidate_kwargs",
    [
        {"candidate_id": "peer:weak", "relationship": "weak_match", "retrieval_rank": 1},
        {
            "candidate_id": "peer:insufficient",
            "relationship": "direct_competitor",
            "retrieval_rank": 1,
            "evidence_sufficient": False,
        },
        {
            "candidate_id": "peer:unpublishable",
            "relationship": "direct_competitor",
            "retrieval_rank": 1,
            "publishable": False,
        },
        {
            "candidate_id": "peer:family",
            "relationship": "direct_competitor",
            "retrieval_rank": 1,
            "family_status": "collision",
        },
        {
            "candidate_id": "peer:ambiguous-family",
            "relationship": "direct_competitor",
            "retrieval_rank": 1,
            "family_status": "ambiguous",
        },
    ],
    ids=["weak", "insufficient", "unpublishable", "family", "ambiguous-family"],
)
def test_weak_or_untrusted_candidate_abstains(
    candidate_kwargs: dict[str, object],
) -> None:
    candidate = PeerCandidate(**candidate_kwargs)  # type: ignore[arg-type]
    assert select_peer([candidate]) == PeerSelection(
        selected_candidate_id=None,
        decision="abstained",
        decision_code="no_publishable_peer",
    )


def test_untrusted_candidate_does_not_veto_a_trusted_alternative() -> None:
    decision = select_peer(
        [
            PeerCandidate(
                "peer:family",
                "direct_competitor",
                1,
                family_status="collision",
            ),
            PeerCandidate("peer:credible", "credible_peer", 9),
        ]
    )

    assert decision.selected_candidate_id == "peer:credible"


def test_equal_rank_is_deterministic_independent_of_input_order() -> None:
    first = PeerCandidate("peer:alpha", "credible_peer", 2)
    second = PeerCandidate("peer:beta", "credible_peer", 2)

    assert select_peer([second, first]) == select_peer([first, second])
    assert select_peer([second, first]).selected_candidate_id == "peer:alpha"


def test_equal_rank_still_prefers_direct_competitor() -> None:
    credible = PeerCandidate("peer:credible", "credible_peer", 2)
    direct = PeerCandidate("peer:direct", "direct_competitor", 2)

    assert select_peer([credible, direct]).selected_candidate_id == "peer:direct"


def test_empty_candidate_set_abstains() -> None:
    assert select_peer([]) == PeerSelection(
        selected_candidate_id=None,
        decision="abstained",
        decision_code="no_publishable_peer",
    )


def test_duplicate_candidate_identity_fails_closed() -> None:
    candidate = PeerCandidate("peer:same", "direct_competitor", 1)

    assert select_peer([candidate, candidate]) == PeerSelection(
        selected_candidate_id=None,
        decision="abstained",
        decision_code="malformed_duplicate_candidate_id",
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"candidate_id": "", "relationship": "credible_peer", "retrieval_rank": 1},
        {"candidate_id": " peer ", "relationship": "credible_peer", "retrieval_rank": 1},
        {"candidate_id": "peer", "relationship": "related", "retrieval_rank": 1},
        {"candidate_id": "peer", "relationship": [], "retrieval_rank": 1},
        {"candidate_id": "peer", "relationship": "credible_peer", "retrieval_rank": 0},
        {"candidate_id": "peer", "relationship": "credible_peer", "retrieval_rank": True},
        {
            "candidate_id": "peer",
            "relationship": "credible_peer",
            "retrieval_rank": 1,
            "family_status": "unknown",
        },
        {
            "candidate_id": "peer",
            "relationship": "credible_peer",
            "retrieval_rank": 1,
            "family_status": [],
        },
    ],
    ids=[
        "empty-id",
        "dirty-id",
        "relationship",
        "relationship-type",
        "zero-rank",
        "bool-rank",
        "family",
        "family-type",
    ],
)
def test_malformed_candidate_is_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(PeerSelectionContractError):
        PeerCandidate(**kwargs)  # type: ignore[arg-type]
