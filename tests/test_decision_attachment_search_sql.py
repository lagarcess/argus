"""The executed decision index derives every decision-level read from the
attachment declaration.

These pins hold the SQL builders that ``PostgresSearchReader.search_rows``
actually executes: the conversation match CTEs, the ledger, and the recall
hydration. Every decision-level read must left-join each attachment a decision
can carry, and every anchored read must discover a decision through its own
note and state and through each attachment's indexed text. Run-scoped counts
keep evidence lineage by contract, and that boundary is pinned too.

The executed proof against a real database is
``tests/test_search_decision_attachment_postgres.py``; these pins only keep the
shape from drifting between runs of that gate.
"""

from __future__ import annotations

import re

import pytest
from argus.domain import postgres_search_reader as reader
from psycopg import sql


def _rendered(composed: sql.Composable) -> str:
    return " ".join(composed.as_string(None).split())


def _between(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin : text.index(end, begin + len(start))]


def _decision_branches(cte: str) -> list[str]:
    branches = re.split(r"\bunion(?: all)?\b", cte)
    assert all("public.decision_notes as decision" in branch for branch in branches)
    return branches


INNER_EVIDENCE_ON_DECISION = re.compile(
    r"(?<!left )join public\.evidence_artifacts as evidence "
    r"on evidence\.id = decision\.evidence_artifact_id"
)


@pytest.mark.parametrize("has_anchor", [False, True], ids=["scan", "anchored"])
def test_match_and_ledger_decision_reads_left_join_every_attachment(
    has_anchor: bool,
) -> None:
    match_ctes = _rendered(reader._conversation_match_ctes(has_anchor=has_anchor))
    ledger = _rendered(reader._conversation_ledger_sql(has_anchor=has_anchor))
    candidates = _between(match_ctes, "decision_candidates as (", " matches as (")
    matching = _between(
        ledger, "decision_matching_conversations as (", "matching_conversations as ("
    )
    expected_branches = 1 + len(reader._DECISION_ATTACHMENTS) if has_anchor else 1

    for cte in (candidates, matching):
        branches = _decision_branches(cte)
        assert len(branches) == expected_branches
        assert not INNER_EVIDENCE_ON_DECISION.search(cte)
        for branch in branches:
            for attachment in reader._DECISION_ATTACHMENTS:
                assert f"{attachment.table} as {attachment.alias}" in branch
        if has_anchor:
            # The decision's own index and each attachment's index discover
            # candidates; the recheck sees the whole haystack in every branch.
            assert (
                "decision_notes as decision on decision.user_id = input.user_id and"
                in (branches[0])
            )
            for attachment, branch in zip(reader._DECISION_ATTACHMENTS, branches[1:], strict=False):
                assert (
                    f"join {attachment.table} as {attachment.alias} "
                    f"on {attachment.alias}.user_id = input.user_id and" in branch
                )
                assert (
                    f"decision.{attachment.decision_key} = {attachment.alias}.id"
                    in branch
                )
        for branch in branches:
            assert "decision_message.content" in branch
            assert "evidence.title" in branch


def test_decision_haystack_and_matched_text_survive_a_missing_attachment() -> None:
    # concat_ws skips nulls, so a decision with one attachment still matches
    # on its note, its state, and the attachment it has.
    assert reader._decision_attachment_text().startswith("concat_ws(' ', ")
    assert "coalesce(decision.note, '')" in reader._decision_haystack_text()
    assert "nullif(decision.note, ''), decision.decision_state" in (
        reader._decision_matched_text()
    )
    for attachment in reader._DECISION_ATTACHMENTS:
        assert attachment.text in reader._decision_attachment_text()
        assert attachment.text in reader._decision_matched_text()


def test_recall_hydration_carries_the_attachment_for_every_decision() -> None:
    hydration = " ".join(reader._CONVERSATION_HYDRATION_SQL.split())
    recall = _between(
        hydration,
        "from public.decision_notes as decision",
        "as latest_recall_decision on true",
    )
    payload = hydration[: hydration.index("as latest_recall_decision on true")]
    payload = payload[payload.rindex("left join lateral (") :]

    for attachment in reader._DECISION_ATTACHMENTS:
        assert (
            f"left join {attachment.table} as {attachment.alias} "
            f"on {attachment.alias}.id = decision.{attachment.decision_key} "
            f"and {attachment.alias}.user_id = %(user_id)s" in recall
        )
    assert "'source_message_id', decision.source_message_id" in payload
    assert "'computation', decision.computation" in payload
    assert f"'attachment_text', {reader._decision_attachment_text()}" in payload


def test_run_scoped_counts_keep_evidence_lineage_by_contract() -> None:
    # decided_runs, latest_run_decided, and the asset rollup count runs, and a
    # run is decided only through its artifact (API contract, section 17).
    hydration = " ".join(reader._CONVERSATION_HYDRATION_SQL.split())
    rollup = _rendered(reader._asset_rollup_ctes())

    assert (
        "join public.decision_notes as decided "
        "on decided.evidence_artifact_id = decided_evidence.id" in hydration
    )
    assert (
        "from public.decision_notes as decision "
        "join public.evidence_artifacts as evidence "
        "on evidence.id = decision.evidence_artifact_id" in hydration
    )
    assert (
        "from public.evidence_artifacts as evidence "
        "join public.decision_notes as decision "
        "on decision.evidence_artifact_id = evidence.id" in rollup
    )
    states = _between(hydration, "select distinct decision.decision_state", ") as states")
    assert "evidence" not in states
