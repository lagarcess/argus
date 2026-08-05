"""Provider-neutral final selection policy for offline peer research."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

Relationship = Literal["direct_competitor", "credible_peer", "weak_match"]
FamilyStatus = Literal["clear", "collision", "ambiguous"]
Decision = Literal["selected", "abstained"]


class PeerSelectionContractError(ValueError):
    """An offline assessment cannot be interpreted safely."""


@dataclass(frozen=True, slots=True)
class PeerCandidate:
    candidate_id: str
    relationship: Relationship
    retrieval_rank: int
    evidence_sufficient: bool = True
    publishable: bool = True
    family_status: FamilyStatus = "clear"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.candidate_id, str)
            or not self.candidate_id
            or self.candidate_id != self.candidate_id.strip()
        ):
            raise PeerSelectionContractError("candidate_id is invalid")
        if not isinstance(self.relationship, str) or self.relationship not in {
            "direct_competitor",
            "credible_peer",
            "weak_match",
        }:
            raise PeerSelectionContractError("relationship is invalid")
        if (
            isinstance(self.retrieval_rank, bool)
            or not isinstance(self.retrieval_rank, int)
            or self.retrieval_rank <= 0
        ):
            raise PeerSelectionContractError("retrieval_rank is invalid")
        if not isinstance(self.evidence_sufficient, bool):
            raise PeerSelectionContractError("evidence_sufficient is invalid")
        if not isinstance(self.publishable, bool):
            raise PeerSelectionContractError("publishable is invalid")
        if not isinstance(self.family_status, str) or self.family_status not in {
            "clear",
            "collision",
            "ambiguous",
        }:
            raise PeerSelectionContractError("family_status is invalid")


@dataclass(frozen=True, slots=True)
class PeerSelection:
    selected_candidate_id: str | None
    decision: Decision
    decision_code: str


def select_peer(candidates: Sequence[PeerCandidate]) -> PeerSelection:
    """Prefer a direct competitor, using frozen retrieval rank within a class."""

    candidate_ids = [candidate.candidate_id for candidate in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        return PeerSelection(
            None,
            "abstained",
            "malformed_duplicate_candidate_id",
        )
    trusted = [
        candidate
        for candidate in candidates
        if candidate.evidence_sufficient
        and candidate.publishable
        and candidate.family_status == "clear"
    ]
    direct = [
        candidate
        for candidate in trusted
        if candidate.relationship == "direct_competitor"
    ]
    credible = [
        candidate for candidate in trusted if candidate.relationship == "credible_peer"
    ]
    eligible = direct or credible
    if not eligible:
        return PeerSelection(None, "abstained", "no_publishable_peer")
    selected = min(
        eligible,
        key=lambda candidate: (candidate.retrieval_rank, candidate.candidate_id),
    )
    return PeerSelection(
        selected.candidate_id,
        "selected",
        f"selected_{selected.relationship}",
    )
