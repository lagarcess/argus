"""Real-Postgres proof for table-safe memory child update triggers."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
psycopg = pytest.importorskip("psycopg")


def _connect():
    return psycopg.connect(DSN, autocommit=True)


def _seed_registered_owner(connection) -> str:
    owner_id = str(uuid.uuid4())
    email = f"memory-trigger-{owner_id[:8]}@example.com"
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id,email,is_anonymous)" " values (%s,%s,false)",
            (owner_id, email),
        )
        cursor.execute(
            "insert into public.profiles (id,email) values (%s,%s)",
            (owner_id, email),
        )
    return owner_id


def _seed_memory_graph(connection, owner_id: str) -> str:
    suffix = uuid.uuid4().hex
    candidate_id = f"candidate-{suffix}"
    receipt_id = f"receipt-{suffix}"
    record_id = f"record-{suffix}"
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.memory_candidates (
              id,
              owner_id,
              category,
              source_label,
              source_value,
              future_benefit,
              trigger,
              proposed_context,
              opt_in_scope,
              sensitivity_status,
              sensitivity_flags,
              sensitivity_policy_version,
              sensitivity_content_digest
            )
            values (
              %s,
              %s,
              'workflow_preference',
              'Show assumptions first',
              'Show assumptions before every result explanation.',
              'Keeps future result reviews consistent.',
              'explicit_request',
              'ordinary',
              array['workflow_preference'],
              'clear',
              '{}'::text[],
              'argus.memory-sensitivity/v1',
              %s
            )
            """,
            (candidate_id, owner_id, f"sha256:{'3' * 64}"),
        )
        cursor.execute(
            """
            insert into public.memory_consent_actions (
              id,
              owner_id,
              action,
              candidate_id,
              requested_scope,
              granted_scope,
              effective_scope,
              idempotency_key
            )
            values (
              %s,
              %s,
              'candidate_confirmation',
              %s,
              array['workflow_preference'],
              array['workflow_preference'],
              array['workflow_preference'],
              %s
            )
            """,
            (receipt_id, owner_id, candidate_id, candidate_id),
        )
        cursor.execute(
            """
            insert into public.memory_records (
              id,
              owner_id,
              candidate_id,
              consent_action_id,
              category,
              label,
              value
            )
            values (
              %s,
              %s,
              %s,
              %s,
              'workflow_preference',
              'Show assumptions first',
              'Show assumptions before every result explanation.'
            )
            """,
            (record_id, owner_id, candidate_id, receipt_id),
        )
        cursor.execute(
            """
            insert into public.memory_prompt_history (
              owner_id,
              category,
              last_proactive_prompt_at,
              updated_at
            )
            values (%s,'workflow_preference',now(),now())
            """,
            (owner_id,),
        )
        cursor.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,
              record_id,
              generation,
              operation,
              status
            )
            values (%s,%s,1,'create','pending')
            """,
            (owner_id, record_id),
        )
        cursor.execute(
            """
            insert into public.memory_provider_projections (
              owner_id,
              record_id,
              provider_ref,
              generation
            )
            values (%s,%s,'provider-original',1)
            """,
            (owner_id, record_id),
        )
        cursor.execute(
            """
            insert into public.memory_provider_cleanup (
              owner_id,
              record_id,
              provider_ref,
              generation
            )
            values (%s,%s,'provider-cleanup',1)
            """,
            (owner_id, record_id),
        )
    return record_id


@pytest.fixture
def memory_graph() -> Iterator[dict[str, str]]:
    with _connect() as connection:
        owner_id = _seed_registered_owner(connection)
        other_owner_id = _seed_registered_owner(connection)
        record_id = _seed_memory_graph(connection, owner_id)
    try:
        yield {
            "owner_id": owner_id,
            "other_owner_id": other_owner_id,
            "record_id": record_id,
        }
    finally:
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.memory_reconciliations" " where owner_id = %s",
                    (owner_id,),
                )
                cursor.execute(
                    "delete from auth.users where id = any(%s::uuid[])",
                    ([owner_id, other_owner_id],),
                )


def test_prompt_history_timestamps_are_mutable(
    memory_graph: dict[str, str],
) -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.memory_prompt_history
                   set last_declined_at = now(),
                       updated_at = now() + interval '1 second'
                 where owner_id = %s
                   and category = 'workflow_preference'
             returning last_declined_at is not null
                """,
                (memory_graph["owner_id"],),
            )
            assert cursor.fetchone() == (True,)


def test_reconciliation_outcome_fields_are_mutable(
    memory_graph: dict[str, str],
) -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.memory_reconciliations
                   set status = 'running',
                       claim_token = 'claim-outcome-fields',
                       lease_expires_at = now() + interval '1 minute',
                       attempt_count = 1
                 where owner_id = %s
                   and record_id = %s
                   and generation = 1
                """,
                (memory_graph["owner_id"], memory_graph["record_id"]),
            )
            cursor.execute(
                """
                update public.memory_reconciliations
                   set status = 'failed',
                       error_code = 'provider_timeout',
                       lease_expires_at = null,
                       completed_at = now()
                 where owner_id = %s
                   and record_id = %s
                   and generation = 1
             returning status,error_code,completed_at is not null
                """,
                (memory_graph["owner_id"], memory_graph["record_id"]),
            )
            assert cursor.fetchone() == ("failed", "provider_timeout", True)


def test_reconciliation_rows_expose_leased_claim_state() -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select column_name
                  from information_schema.columns
                 where table_schema = 'public'
                   and table_name = 'memory_reconciliations'
                   and column_name in (
                     'claim_token',
                     'lease_expires_at',
                     'attempt_count'
                   )
                 order by column_name
                """
            )
            assert tuple(row[0] for row in cursor.fetchall()) == (
                "attempt_count",
                "claim_token",
                "lease_expires_at",
            )


def test_pending_reconciliation_cannot_skip_claim_to_terminal(
    memory_graph: dict[str, str],
) -> None:
    with _connect() as connection:
        with pytest.raises(
            psycopg.errors.CheckViolation,
            match="transition",
        ):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.memory_reconciliations
                       set status = 'failed',
                           error_code = 'provider_timeout',
                           completed_at = now()
                     where owner_id = %s
                       and record_id = %s
                       and generation = 1
                    """,
                    (memory_graph["owner_id"], memory_graph["record_id"]),
                )


def test_running_reconciliation_requires_exact_claim_shape(
    memory_graph: dict[str, str],
) -> None:
    with _connect() as connection:
        with pytest.raises(
            psycopg.errors.CheckViolation,
            match="claim",
        ):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.memory_reconciliations
                       set status = 'running'
                     where owner_id = %s
                       and record_id = %s
                       and generation = 1
                    """,
                    (memory_graph["owner_id"], memory_graph["record_id"]),
                )


def test_succeeded_reconciliation_forbids_error_code(
    memory_graph: dict[str, str],
) -> None:
    with _connect() as connection:
        with pytest.raises(
            psycopg.errors.CheckViolation,
            match="succeeded",
        ):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.memory_reconciliations
                       set status = 'succeeded',
                           error_code = 'must-not-survive',
                           completed_at = now()
                     where owner_id = %s
                       and record_id = %s
                       and generation = 1
                    """,
                    (memory_graph["owner_id"], memory_graph["record_id"]),
                )


def test_failed_reconciliation_requires_bounded_error_code(
    memory_graph: dict[str, str],
) -> None:
    with _connect() as connection:
        with pytest.raises(
            psycopg.errors.CheckViolation,
            match="failed",
        ):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.memory_reconciliations
                       set status = 'failed',
                           completed_at = now()
                     where owner_id = %s
                       and record_id = %s
                       and generation = 1
                    """,
                    (memory_graph["owner_id"], memory_graph["record_id"]),
                )


def test_provider_projection_derivative_fields_are_mutable(
    memory_graph: dict[str, str],
) -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.memory_provider_projections
                   set provider_ref = 'provider-updated',
                       generation = 2,
                       updated_at = updated_at + interval '1 second'
                 where owner_id = %s
                   and record_id = %s
             returning provider_ref,generation
                """,
                (memory_graph["owner_id"], memory_graph["record_id"]),
            )
            assert cursor.fetchone() == ("provider-updated", 2)


def test_provider_cleanup_resolution_fields_are_mutable(
    memory_graph: dict[str, str],
) -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.memory_provider_cleanup
                   set status = 'resolved',
                       resolved_at = now()
                 where owner_id = %s
                   and record_id = %s
                   and provider_ref = 'provider-cleanup'
                   and generation = 1
             returning status,resolved_at is not null
                """,
                (memory_graph["owner_id"], memory_graph["record_id"]),
            )
            assert cursor.fetchone() == ("resolved", True)


def test_prompt_history_owner_and_category_remain_immutable(
    memory_graph: dict[str, str],
) -> None:
    updates = (
        (
            "owner_id",
            memory_graph["other_owner_id"],
        ),
        (
            "category",
            "personalization_preference",
        ),
    )
    with _connect() as connection:
        for column, value in updates:
            with pytest.raises(psycopg.errors.CheckViolation, match="immutable"):
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"update public.memory_prompt_history set {column}=%s"
                        " where owner_id=%s and category='workflow_preference'",
                        (value, memory_graph["owner_id"]),
                    )


def test_reconciliation_owner_record_and_generation_remain_immutable(
    memory_graph: dict[str, str],
) -> None:
    updates = (
        ("owner_id", memory_graph["other_owner_id"]),
        ("record_id", f"record-{uuid.uuid4()}"),
        ("generation", 2),
    )
    with _connect() as connection:
        for column, value in updates:
            with pytest.raises(psycopg.errors.CheckViolation, match="immutable"):
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"update public.memory_reconciliations set {column}=%s"
                        " where owner_id=%s and record_id=%s and generation=1",
                        (
                            value,
                            memory_graph["owner_id"],
                            memory_graph["record_id"],
                        ),
                    )


def test_provider_projection_owner_and_record_remain_immutable(
    memory_graph: dict[str, str],
) -> None:
    updates = (
        ("owner_id", memory_graph["other_owner_id"]),
        ("record_id", f"record-{uuid.uuid4()}"),
    )
    with _connect() as connection:
        for column, value in updates:
            with pytest.raises(psycopg.errors.CheckViolation, match="immutable"):
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"update public.memory_provider_projections set {column}=%s"
                        " where owner_id=%s and record_id=%s",
                        (
                            value,
                            memory_graph["owner_id"],
                            memory_graph["record_id"],
                        ),
                    )


def test_provider_cleanup_identity_remains_immutable(
    memory_graph: dict[str, str],
) -> None:
    updates = (
        ("owner_id", memory_graph["other_owner_id"]),
        ("record_id", f"record-{uuid.uuid4()}"),
        ("provider_ref", "provider-other"),
        ("generation", 2),
    )
    with _connect() as connection:
        for column, value in updates:
            with pytest.raises(psycopg.errors.CheckViolation, match="immutable"):
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"update public.memory_provider_cleanup set {column}=%s"
                        " where owner_id=%s and record_id=%s"
                        " and provider_ref='provider-cleanup' and generation=1",
                        (
                            value,
                            memory_graph["owner_id"],
                            memory_graph["record_id"],
                        ),
                    )


def test_child_identity_trigger_rejects_unknown_table_names() -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                create temporary table unexpected_memory_child (
                  owner_id uuid not null,
                  marker text not null
                )
                """
            )
            cursor.execute(
                """
                create trigger protect_unexpected_memory_child
                before update on unexpected_memory_child
                for each row execute function
                  argus_private.protect_memory_child_identity()
                """
            )
            cursor.execute(
                "insert into unexpected_memory_child (owner_id,marker)"
                " values (%s,'before')",
                (str(uuid.uuid4()),),
            )
            with pytest.raises(
                psycopg.errors.CheckViolation,
                match="unsupported memory child table",
            ):
                cursor.execute("update unexpected_memory_child set marker='after'")
