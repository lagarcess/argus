"""Real SQL scope and append-only permissions after the research ledger migration."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN, reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured"
)
psycopg = pytest.importorskip("psycopg")


@pytest.mark.parametrize(
    ("source", "feature_area", "nullable"),
    [
        ("research", "research_rail", True),
        ("research", "discovery", False),
        ("api_turn", "research_rail", False),
        ("render_workflow", "result_readout", False),
    ],
)
def test_only_research_rail_accepts_explicit_null_status(source, feature_area, nullable):
    with psycopg.connect(DSN) as connection:
        try:
            connection.execute("set local role service_role")
            insert = (
                "insert into public.cost_ledger_entries "
                "(source,service,provider,feature_area,correlation_id,status) "
                "values (%s,'test','test',%s,%s,%s) returning status"
            )
            args = (source, feature_area, str(uuid4()))
            if nullable:
                assert connection.execute(insert, (*args, None)).fetchone() == (None,)
            else:
                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.transaction():
                        connection.execute(insert, (*args, None))
            # Valid old inserts still work; the existing status vocabulary stays enforced.
            assert connection.execute(insert, (*args, "failed")).fetchone() == ("failed",)
            with pytest.raises(psycopg.errors.CheckViolation):
                with connection.transaction():
                    connection.execute(insert, (*args, "invented"))
            assert connection.execute(
                "select has_table_privilege(current_user,'public.cost_ledger_entries','SELECT'), "
                "has_table_privilege(current_user,'public.cost_ledger_entries','INSERT'), "
                "has_table_privilege(current_user,'public.cost_ledger_entries','UPDATE'), "
                "has_table_privilege(current_user,'public.cost_ledger_entries','DELETE')"
            ).fetchone() == (True, True, False, False)
        finally:
            connection.rollback()


def test_omitted_sql_status_keeps_the_legacy_default_and_unversioned_metadata():
    with psycopg.connect(DSN) as connection:
        try:
            row = connection.execute(
                "insert into public.cost_ledger_entries "
                "(source,service,provider,feature_area,correlation_id) "
                "values ('research','test','test','research_rail',%s) returning status,metadata",
                (str(uuid4()),),
            ).fetchone()
            assert row == ("succeeded", {})
        finally:
            connection.rollback()
