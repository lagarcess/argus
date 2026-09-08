"""Real SQL proof for the private observation store on disposable PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.stages.clarify import clarify_stage
from argus.observability.refusal_log import RefusalObservation
from faker import Faker

from tests.agent_runtime.test_unsupported_fallback_honesty import (
    MOMENTUM_MESSAGE,
    RecordingClarifier,
    _unsupported_state,
)

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN, reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured"
)
psycopg = pytest.importorskip("psycopg")
fake = Faker()


@pytest.fixture
def database() -> Iterator[tuple[Any, dict[str, str]]]:
    with psycopg.connect(DSN) as connection:
        owner = {
            key: fake.uuid4() for key in ("user_id", "conversation_id", "request_id")
        }
        email = fake.email()
        connection.execute(
            "insert into auth.users (id, email) values (%s, %s)",
            (owner["user_id"], email),
        )
        connection.execute(
            "insert into public.profiles (id, email) values (%s, %s)",
            (owner["user_id"], email),
        )
        connection.execute(
            "insert into public.conversations (id, user_id, title) values (%s, %s, %s)",
            (owner["conversation_id"], owner["user_id"], fake.sentence()),
        )
        try:
            yield connection, owner
        finally:
            connection.rollback()


def _message(
    connection: Any,
    owner: dict[str, str],
    *,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    message_id = fake.uuid4()
    connection.execute(
        "insert into public.messages (id, user_id, conversation_id, role, content, metadata)"
        " values (%s, %s, %s, %s, %s, %s)",
        (
            message_id,
            owner["user_id"],
            owner["conversation_id"],
            role,
            content,
            psycopg.types.json.Jsonb(metadata or {}),
        ),
    )
    return message_id


def _insert(connection: Any, observation: RefusalObservation) -> None:
    from psycopg import sql
    from psycopg.types.json import Jsonb

    row = observation.model_dump()
    connection.execute(
        sql.SQL("insert into public.refusal_observations ({}) values ({})").format(
            sql.SQL(", ").join(map(sql.Identifier, row)),
            sql.SQL(", ").join(sql.Placeholder() for _ in row),
        ),
        [Jsonb(value) if isinstance(value, dict) else value for value in row.values()],
    )


def _linked(
    connection: Any,
    owner: dict[str, str],
    *,
    asked: str | None = None,
    response: str | None = None,
    outcome: dict[str, Any] | None = None,
    action: dict[str, Any] | None = None,
) -> RefusalObservation:
    request_id = _message(
        connection,
        owner,
        role="user",
        content=asked or fake.sentence(),
        metadata={"chat_action": action} if action else {},
    )
    response_id = _message(
        connection,
        owner,
        role="assistant",
        content=response or fake.sentence(),
        metadata=outcome,
    )
    return RefusalObservation(
        **owner, request_message_id=request_id, response_message_id=response_id
    )


def test_terminal_refusal_is_readable_with_its_exact_shape_and_question(
    database: tuple[Any, dict[str, str]],
) -> None:
    connection, owner = database
    result = clarify_stage(
        state=_unsupported_state(
            message=MOMENTUM_MESSAGE,
            category="unsupported_strategy_logic",
            raw_value="a momentum breakout strategy",
            explanation="Momentum breakout rules are not executable yet.",
        ),
        contract=build_default_capability_contract(),
        clarification_generator=RecordingClarifier(None),
        language="en",
    )
    asked, response = MOMENTUM_MESSAGE, result.patch["assistant_prompt"]
    outcome = {key: result.patch[key] for key in ("response_intent", "clarification")}
    assert outcome["clarification"]["kind"] == "unsupported_recovery"
    action = {"type": fake.word(), "payload": {fake.word(): fake.uuid4()}}
    observation = _linked(
        connection, owner, asked=asked, response=response, outcome=outcome, action=action
    )
    _insert(connection, observation)
    # An interleaved unrelated message cannot change this exact pair's readback.
    _message(connection, owner, role="user", content=fake.sentence())

    connection.execute("set local role service_role")
    row = connection.execute(
        "select asked, action, outcome, response from public.refusal_log where id = %s",
        (observation.id,),
    ).fetchone()
    assert row == (asked, action, outcome, response)


def test_frequency_groups_existing_fields_and_counts_reused_request_ids(
    database: tuple[Any, dict[str, str]],
) -> None:
    connection, owner = database
    code = fake.word()
    for _ in range(2):
        _insert(
            connection,
            RefusalObservation(
                **owner,
                asked=fake.sentence(),
                action={"type": "refine_idea"},
                outcome={"code": code},
                status_code=409,
            ),
        )
    linked = _linked(connection, owner, outcome={"recovery": {"code": code}})
    _insert(connection, linked)

    assert connection.execute(
        "select outcome ->> 'code', count(*) from public.refusal_log"
        " where user_id = %s and status_code = 409 group by outcome ->> 'code'",
        (owner["user_id"],),
    ).fetchall() == [(code, 2)]
    assert connection.execute(
        "select outcome #>> '{recovery,code}', count(*) from public.refusal_log"
        " where user_id = %s and response_message_id is not null"
        " group by outcome #>> '{recovery,code}'",
        (owner["user_id"],),
    ).fetchall() == [(code, 1)]
    with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
        _insert(connection, linked.model_copy(update={"id": fake.uuid4()}))


@pytest.mark.parametrize("role", ["anon", "authenticated"])
@pytest.mark.parametrize("surface", ["refusal_observations", "refusal_log"])
def test_client_roles_cannot_read_private_content(
    database: tuple[Any, dict[str, str]], role: str, surface: str
) -> None:
    from psycopg import sql

    connection, owner = database
    _insert(connection, _linked(connection, owner))
    with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
        connection.execute(sql.SQL("set local role {}").format(sql.Identifier(role)))
        connection.execute(
            sql.SQL("select * from public.{}").format(sql.Identifier(surface))
        )


def test_service_role_can_insert_and_read_but_cannot_mutate(
    database: tuple[Any, dict[str, str]],
) -> None:
    connection, owner = database
    observation = _linked(connection, owner)
    connection.execute("set local role service_role")
    _insert(connection, observation)
    assert connection.execute(
        "select id from public.refusal_log where id = %s", (observation.id,)
    ).fetchone()
    for operation in (
        "update public.refusal_observations set request_id = 'changed'",
        "delete from public.refusal_observations",
    ):
        with (
            pytest.raises(psycopg.errors.InsufficientPrivilege),
            connection.transaction(),
        ):
            connection.execute(operation)


@pytest.mark.parametrize(
    "changed_field",
    ["user_id", "conversation_id", "request_message_id", "response_message_id"],
)
def test_linked_pair_rejects_wrong_owner_conversation_or_message_roles(
    database: tuple[Any, dict[str, str]], changed_field: str
) -> None:
    connection, owner = database
    observation = _linked(connection, owner)
    wrong_value = (
        fake.uuid4()
        if changed_field in {"user_id", "conversation_id"}
        else getattr(
            observation,
            "response_message_id"
            if changed_field == "request_message_id"
            else "request_message_id",
        )
    )
    with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
        _insert(connection, observation.model_copy(update={changed_field: wrong_value}))


def test_rejected_target_is_a_claim_and_never_joins_other_users_messages(
    database: tuple[Any, dict[str, str]],
) -> None:
    connection, owner = database
    foreign_owner = fake.uuid4()
    supplied_target, foreign_message = fake.uuid4(), fake.uuid4()
    connection.execute(
        "insert into auth.users (id, email) values (%s, %s)",
        (foreign_owner, fake.email()),
    )
    connection.execute(
        "insert into public.profiles (id, email) values (%s, %s)",
        (foreign_owner, fake.email()),
    )
    connection.execute(
        "insert into public.conversations (id, user_id, title) values (%s, %s, %s)",
        (supplied_target, foreign_owner, fake.sentence()),
    )
    connection.execute(
        "insert into public.messages (id, user_id, conversation_id, role, content)"
        " values (%s, %s, %s, 'assistant', %s)",
        (foreign_message, foreign_owner, supplied_target, fake.sentence()),
    )
    observation = RefusalObservation(
        **{**owner, "conversation_id": supplied_target},
        asked=fake.sentence(),
        action={"payload": {"source_assistant_id": foreign_message}},
        outcome={"code": fake.word()},
        status_code=404,
    )
    _insert(connection, observation)
    assert connection.execute(
        "select conversation_id, request_message_id, response_message_id, asked, response"
        " from public.refusal_log where id = %s",
        (observation.id,),
    ).fetchone() == (supplied_target, None, None, observation.asked, None)


def test_view_does_not_bypass_rls_if_read_grants_are_later_added(
    database: tuple[Any, dict[str, str]],
) -> None:
    connection, owner = database
    _insert(connection, _linked(connection, owner))
    # Transaction-scoped grants prove the invoker view retains table RLS defense.
    connection.execute(
        "grant select on public.refusal_log, public.refusal_observations,"
        " public.messages to authenticated"
    )
    connection.execute("set local role authenticated")
    assert connection.execute("select * from public.refusal_log").fetchall() == []


@pytest.mark.parametrize("deleted", ["request", "response", "owner"])
def test_content_retention_follows_message_and_owner_deletion(
    database: tuple[Any, dict[str, str]], deleted: str
) -> None:
    connection, owner = database
    linked = _linked(connection, owner)
    _insert(connection, linked)
    rejected = RefusalObservation(
        **owner, asked=fake.sentence(), outcome={"code": fake.word()}, status_code=400
    )
    _insert(connection, rejected)
    if deleted == "owner":
        connection.execute("delete from auth.users where id = %s", (owner["user_id"],))
    else:
        message_id = (
            linked.request_message_id
            if deleted == "request"
            else linked.response_message_id
        )
        connection.execute("delete from public.messages where id = %s", (message_id,))
    remaining = connection.execute(
        "select id::text from public.refusal_log where user_id = %s", (owner["user_id"],)
    ).fetchall()
    assert remaining == ([] if deleted == "owner" else [(rejected.id,)])
