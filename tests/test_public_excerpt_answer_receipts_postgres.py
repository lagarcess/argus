"""Plain answers use the existing snapshot constraints and deletion lifecycle."""

from __future__ import annotations

import pytest
from argus.api.public_excerpt_schemas import (
    PublicExcerptAnswerTurn,
    PublicExcerptTurnsPayload,
)

from tests.test_public_excerpt_calculation_receipts_postgres import DSN, _ComputedAnswer

pytestmark = pytest.mark.skipif(
    not DSN, reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured"
)
psycopg = pytest.importorskip("psycopg")


def test_plain_answer_kind_is_frozen_and_source_delete_revokes():
    with psycopg.connect(DSN) as connection:
        try:
            source = _ComputedAnswer(connection.cursor()).seed()
            payload = PublicExcerptTurnsPayload(
                turns=[
                    PublicExcerptAnswerTurn(
                        question="What does diversification mean?",
                        answer="Spreading money across different investments.",
                        content_language="en",
                    )
                ]
            ).model_dump(mode="json")
            receipt_id = source.insert_receipt(kind="answer", payload=payload)
            assert connection.execute(
                "select kind, payload from public.public_excerpt_snapshots where id=%s",
                (receipt_id,),
            ).fetchone() == ("answer", payload)
            with pytest.raises(psycopg.errors.CheckViolation):
                with connection.transaction():
                    connection.execute(
                        "update public.public_excerpt_snapshots set kind='research_answer' where id=%s",
                        (receipt_id,),
                    )
            connection.execute(
                "delete from public.messages where id=%s", (source.message_id,)
            )
            assert connection.execute(
                "select revoked_at is not null, revocation_reason from public.public_excerpt_snapshots where id=%s",
                (receipt_id,),
            ).fetchone() == (True, "source_deleted")
        finally:
            connection.rollback()
