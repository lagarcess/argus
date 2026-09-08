"""The durable decision index recalls a computed-answer decision through its answer.

The Postgres reader is the memory index's durable twin. Both find a decision by
its note and state; a backtest decision also by its evidence title and digest,
and a computed-answer decision by the assistant message it attaches to. These
pins hold the SQL to that rule without a database.
"""

from __future__ import annotations

from argus.domain import postgres_search_reader as reader


def _normalized(text: str) -> str:
    return " ".join(text.lower().split())


def test_late_decision_source_joins_the_answer_message_and_carries_the_attachment() -> (
    None
):
    source = reader._LATE_DECISION

    joins = _normalized(source.joins)
    assert "left join public.messages as decision_message" in joins
    assert "on decision_message.id = decision.source_message_id" in joins
    assert "and decision_message.user_id = input.user_id" in joins
    assert "nullif(decision_message.content, '')" in _normalized(source.title_expression)
    assert "decision_message.content" in _normalized(source.matched_expression)
    assert "decision_message.content" in _normalized(source.haystack_expression)
    payload = _normalized(source.payload_expression)
    assert "'source_message_id', decision.source_message_id" in payload
    assert "'computation', decision.computation" in payload


def test_conversation_hydration_carries_the_recall_decision_attachment() -> None:
    sql = _normalized(reader._CONVERSATION_HYDRATION_SQL)
    recall_block = sql.split(") as latest_recall_decision on true", 1)[0]
    recall_block = recall_block.rsplit("left join lateral (", 1)[1]

    assert "'source_message_id', decision.source_message_id" in recall_block
    assert "'computation', decision.computation" in recall_block
    assert "'attachment_text', decision_message.content" in recall_block
    assert "left join public.messages as decision_message" in recall_block
    assert "on decision_message.id = decision.source_message_id" in recall_block
    assert "and decision_message.user_id = %(user_id)s" in recall_block
    # The evidence lineage stays optional: a computed-answer decision has none.
    assert "left join public.evidence_artifacts as evidence" in recall_block


def test_conversation_decision_state_aggregate_needs_no_evidence_lineage() -> None:
    sql = _normalized(reader._CONVERSATION_HYDRATION_SQL)
    states_block = sql.split(") as decision_summary on true", 1)[0]
    states_block = states_block.rsplit("left join lateral (", 1)[1]

    assert "from public.decision_notes as decision" in states_block
    assert "evidence" not in states_block
