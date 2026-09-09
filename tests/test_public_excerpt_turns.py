"""Selection receipts use the real owner service and one frozen public contract."""

from uuid import uuid4

import pytest
from argus.api import public_excerpts as service
from argus.api import state as api_state
from argus.api.schemas import Message
from argus.domain.public_excerpts import PublicExcerptSourceError
from pydantic import ValidationError

from tests.public_excerpt_factories import build_conversation, utc


@pytest.fixture
def owner(monkeypatch):
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    api_state.store.reset()
    user = api_state.store.get_or_create_dev_user()
    conversation = build_conversation()
    api_state.store.conversations[conversation.id] = conversation
    api_state.store.conversation_owners[conversation.id] = user.id
    return user, conversation


def add_pair(
    owner,
    *,
    index=0,
    metadata=None,
    question="Why did AAPL rise?",
    answer="Revenue grew **ten percent**.",
):
    user, conversation = owner
    research = {
        "schema_version": "argus_research/v1",
        "shape": "balanced",
        "sources": [
            {
                "title": "Apple results",
                "domain": "apple.com",
                "url": "https://apple.com/newsroom/results",
                "source_date": "2026-08-06",
            }
        ],
        "retrieved_at": utc().isoformat(),
        "anchor_symbols": ["AAPL"],
        "asset_class": "equity",
    }
    common = dict(conversation_id=conversation.id)
    request = Message(
        id=str(uuid4()),
        role="user",
        content=question,
        created_at=utc(index * 2),
        **common,
    )
    response = Message(
        id=str(uuid4()),
        role="assistant",
        content=answer,
        created_at=utc(index * 2 + 1),
        metadata=metadata
        if metadata is not None
        else {
            "agent_runtime_turn": {"terminal": True, "status": "completed"},
            "research": research,
        },
        **common,
    )
    api_state.store.messages.setdefault(conversation.id, []).extend([request, response])
    return request, response


def preview(owner, messages, note=None):
    assert hasattr(
        service, "preview_receipt_for_messages"
    ), "shared message preview service is missing"
    user, conversation = owner
    return service.preview_receipt_for_messages(
        user=user,
        conversation_id=conversation.id,
        message_ids=[m.id for m in messages],
        owner_note=note,
    )


def create(owner, messages, document, note=None):
    user, conversation = owner
    return service.create_receipt_for_messages(
        user=user,
        conversation_id=conversation.id,
        message_ids=[m.id for m in messages],
        owner_note=note,
        expected_digest=document.payload_digest,
    )


def test_preview_is_exact_closed_frozen_document_without_side_effects(owner):
    _, answer = add_pair(owner, question="  Why\n did AAPL rise? ")
    result = preview(owner, [answer])
    assert result.payload.schema_version == 2
    assert result.payload.kind == "turns"
    leaf = result.payload.turns[0]
    assert leaf.question == "Why did AAPL rise?"
    assert leaf.answer == answer.content
    assert set(leaf.model_dump()) == {
        "kind",
        "question",
        "answer",
        "sources",
        "retrieved_at",
        "anchor_symbols",
        "asset_class",
        "offered_next_step",
        "owner_note",
        "content_language",
        "framing",
        "provenance_mark",
    }
    assert not api_state.store.public_excerpt_snapshots
    snapshot, created = create(owner, [answer], result)
    assert created
    assert snapshot.payload == result.payload
    assert snapshot.payload_digest == result.payload_digest
    again, created = create(owner, [answer], result)
    assert not created and again.id == snapshot.id


@pytest.mark.parametrize("count", [0, 1, 4, 5])
def test_selection_bounds_and_canonical_order(owner, count):
    answers = [add_pair(owner, index=i)[1] for i in range(count)]
    if count in (0, 5):
        with pytest.raises(PublicExcerptSourceError):
            preview(owner, answers)
    else:
        result = preview(owner, answers[::-1])
        assert len(result.payload.turns) == count
        assert result.payload.turns[0].answer == answers[0].content


@pytest.mark.parametrize(
    "mutation,reason",
    [
        (lambda m: m.update(memory_recalls=[{}]), "memory_used"),
        (lambda m: m["research"].update(degraded=True), "degraded"),
        (lambda m: m["research"].update(sources=[]), "missing_sources"),
        (lambda m: m["research"].update(shape="fast"), "unsupported_shape"),
        (lambda m: m["research"].update(shape="find"), "unsupported_shape"),
        (lambda m: m["research"].update(shape="personal_money"), "unsupported_shape"),
        (lambda m: m["agent_runtime_turn"].update(terminal=False), "not_completed"),
        (lambda m: m.update(confirmation={}), "unsupported_turn"),
    ],
)
def test_refusal_refuses_whole_selection_and_candidates_name_reason(
    owner, mutation, reason
):
    _, eligible = add_pair(owner)
    _, other = add_pair(owner, index=1)
    mutation(other.metadata)
    with pytest.raises(PublicExcerptSourceError) as error:
        preview(owner, [eligible, other])
    assert error.value.reason == reason
    assert not api_state.store.public_excerpt_snapshots
    candidates = service.receipt_candidates(user=owner[0], conversation_id=owner[1].id)
    assert candidates.max_turns == 4
    assert candidates.items[1].reason == reason
    assert not candidates.items[1].eligible


@pytest.mark.parametrize("field", ["question", "answer", "owner_note"])
@pytest.mark.parametrize(
    "unsafe",
    [
        "record 12345678-1234-4123-8123-123456789abc",
        "Bearer secret",
        "supabase record",
        "abcdefghijklmnopqrstuvwxyzABCDEF",
        "sk-abcdefghi",
    ],
)
def test_every_prose_field_shares_identifier_and_secret_audit(owner, field, unsafe):
    kwargs = {field: unsafe} if field != "owner_note" else {}
    _, answer = add_pair(owner, **kwargs)
    with pytest.raises(PublicExcerptSourceError) as error:
        preview(owner, [answer], unsafe if field == "owner_note" else None)
    assert error.value.field == field


@pytest.mark.parametrize(
    "field,length", [("question", 501), ("answer", 4001), ("owner_note", 281)]
)
def test_field_bounds_refuse_without_truncation(owner, field, length):
    value = ("short " * length)[:length]
    _, answer = add_pair(owner, **({field: value} if field != "owner_note" else {}))
    with pytest.raises(PublicExcerptSourceError) as error:
        preview(owner, [answer], value if field == "owner_note" else None)
    assert error.value.field == field
    assert error.value.reason == "text_too_long"


@pytest.mark.parametrize(
    "answer",
    [
        "[source](https://evil.test/x)",
        "<https://evil.test/x>",
        "[source][ref]\n\n[ref]: https://evil.test/x",
        "![image](https://evil.test/x)",
        "<a href='https://evil.test/x'>x</a>",
        "Read https://evil.test/x",
    ],
)
def test_all_url_destinations_must_be_verbatim_typed_sources(owner, answer):
    _, message = add_pair(owner, answer=answer)
    with pytest.raises(PublicExcerptSourceError) as error:
        preview(owner, [message])
    assert error.value.field == "answer"
    assert error.value.reason == "unlisted_url"


def test_listed_markdown_link_preserved_and_next_step_reads_typed_symbols(owner):
    _, message = add_pair(owner, answer="[Apple](https://apple.com/newsroom/results)")
    message.metadata["next_experiments"] = {
        "rows": [
            {
                "kind": "research_test_single",
                "label": "wrong TSLA",
                "send_text": "MSFT",
                "label_parts": [{"type": "ticker", "value": "AAPL"}],
            }
        ]
    }
    leaf = preview(owner, [message]).payload.turns[0]
    assert leaf.answer == message.content
    assert leaf.offered_next_step.symbols == ["AAPL"]
    message.metadata["next_experiments"]["rows"][0]["kind"] = "unknown_future_kind"
    assert preview(owner, [message]).payload.turns[0].offered_next_step is None


def test_preview_drift_refuses_and_existing_live_preview_returns_stored_note(owner):
    _, message = add_pair(owner)
    first = preview(owner, [message], "First note")
    message.content = "Revenue grew twenty percent."
    with pytest.raises(PublicExcerptSourceError) as error:
        create(owner, [message], first, "First note")
    assert error.value.reason == "preview_changed"
    current = preview(owner, [message], "First note")
    snapshot, _ = create(owner, [message], current, "First note")
    existing = preview(owner, [message], "Another note")
    assert existing.payload == snapshot.payload
    assert existing.existing_receipt.id == snapshot.id


def test_closed_nested_models_reject_extra_source_fields(owner):
    _, message = add_pair(owner)
    result = preview(owner, [message])
    document = result.payload.model_dump(mode="json")
    document["turns"][0]["sources"][0]["message_id"] = "private"
    with pytest.raises(ValidationError):
        type(result.payload).model_validate(document)


def test_duplicate_and_foreign_message_selection_refuses(owner):
    _, message = add_pair(owner)
    with pytest.raises(PublicExcerptSourceError):
        preview(owner, [message, message])
    foreign = message.model_copy(
        update={"id": str(uuid4()), "conversation_id": str(uuid4())}
    )
    with pytest.raises(PublicExcerptSourceError):
        preview(owner, [message, foreign])


def test_owner_candidate_preview_create_routes_and_drift(owner, monkeypatch):
    from argus.api.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED", "true")
    _, message = add_pair(owner)
    base = f"/api/v1/conversations/{owner[1].id}/public-excerpt"
    client = TestClient(app)
    candidates = client.get(base + "-candidates")
    assert candidates.status_code == 200, candidates.text
    assert candidates.json()["max_turns"] == 4
    body = {"message_ids": [message.id]}
    preview_response = client.post(base + "-preview", json=body)
    assert preview_response.status_code == 200, preview_response.text
    created = client.post(
        base, json={**body, "payload_digest": preview_response.json()["payload_digest"]}
    )
    assert created.status_code == 200, created.text
    assert created.json()["receipt"]["kind"] == "research_answer"
    assert (
        client.get(
            "/api/v1/public/receipts/" + created.json()["receipt"]["public_id"]
        ).json()["payload"]
        == preview_response.json()["payload"]
    )


@pytest.mark.parametrize("suffix", ["", "-preview", "-candidates"])
def test_selection_routes_flag_off_byte_identity(owner, monkeypatch, suffix):
    from argus.api.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED", "false")
    client = TestClient(app)
    reference = client.get("/api/v1/absent-share-answer")
    response = client.post(
        f"/api/v1/conversations/bad-id/public-excerpt{suffix}", content="invalid json"
    )
    assert response.status_code == reference.status_code
    assert response.content == reference.content


def test_guest_handoff_share_pending_action_requires_canonical_message():
    from argus.api.schemas import GuestPendingAction

    common = {
        "reason": "share_result",
        "conversation_id": str(uuid4()),
        "action_id": str(uuid4()),
    }
    message_id = str(uuid4())
    action = GuestPendingAction.model_validate({**common, "message_id": message_id})
    assert action.message_id == message_id
    with pytest.raises(ValidationError):
        GuestPendingAction.model_validate(common)
    with pytest.raises(ValidationError):
        GuestPendingAction.model_validate(
            {**common, "reason": "keep_history", "message_id": message_id}
        )


@pytest.mark.parametrize("status", ["succeeded", "running", "failed"])
def test_background_research_uses_canonical_job_settlement_and_original_question(
    owner, status
):
    from argus.domain.job_settlement import RESEARCH_OPERATION_SCOPE

    request, response = add_pair(owner)
    response.metadata.pop("agent_runtime_turn")
    # Another user message between dispatch and answer cannot become its question.
    later_request, _ = add_pair(owner, index=1, question="A different question")
    response.created_at = utc(5)
    job_id = str(uuid4())
    api_state.store.backtest_jobs[job_id] = {
        "id": job_id,
        "user_id": owner[0].id,
        "conversation_id": owner[1].id,
        "operation_scope": RESEARCH_OPERATION_SCOPE,
        "status": status,
        "request_message_id": request.id,
        "execution_metadata": {"research_result_message_id": response.id},
    }
    if status == "succeeded":
        assert preview(owner, [response]).payload.turns[0].question == request.content
    else:
        with pytest.raises(PublicExcerptSourceError) as error:
            preview(owner, [response])
        assert error.value.reason == "not_completed"


def seed_backtest(owner):
    from tests.public_excerpt_factories import (
        build_artifact,
        build_run,
        seed_result_messages,
    )

    artifact, run = build_artifact(), build_run()
    store = api_state.store
    store.evidence_artifacts[artifact.id] = artifact
    store.evidence_artifact_owners[artifact.id] = owner[0].id
    store.backtest_runs[run.id] = run
    store.backtest_run_owners[run.id] = owner[0].id
    messages = seed_result_messages(store, run)
    return artifact, run, messages[-1]


def test_artifact_shortcut_turn_and_historical_v1_keep_one_lineage(owner):
    from argus.api.public_excerpt_schemas import PUBLIC_EXCERPT_DOCUMENT_ADAPTER
    from argus.domain.public_excerpts import build_public_excerpt_payload, payload_digest

    artifact, run, message = seed_backtest(owner)
    first = preview(owner, [message])
    snapshot, _ = service.create_receipt_for_artifact(
        user=owner[0], artifact_id=artifact.id, owner_note=None
    )
    assert create(owner, [message], first)[0].id == snapshot.id
    service.public_excerpt_repository().revoke_public_excerpt_snapshot(
        owner_id=owner[0].id, snapshot_id=snapshot.id
    )
    legacy = build_public_excerpt_payload(
        artifact=artifact,
        run_chart=run.chart,
        run_config_snapshot=run.config_snapshot,
        owner_note="Legacy",
        content_language="en",
    )
    raw = legacy.model_dump_json()
    assert PUBLIC_EXCERPT_DOCUMENT_ADAPTER.validate_json(raw).model_dump_json() == raw
    saved = snapshot.model_copy(
        update={
            "id": str(uuid4()),
            "payload": legacy,
            "payload_digest": payload_digest(legacy),
            "selection_key": None,
            "source_message_ids": [],
        }
    )
    api_state.store.public_excerpt_snapshots[saved.id] = saved
    assert preview(owner, [message], "Different").payload.model_dump_json() == raw
    assert (
        service.create_receipt_for_artifact(
            user=owner[0], artifact_id=artifact.id, owner_note=None
        )[0].id
        == saved.id
    )


def test_backtest_uses_shared_display_figures_and_closed_config(owner):
    from argus.domain.result_figures import result_display_figures

    artifact, run, message = seed_backtest(owner)
    run.metrics["aggregate"]["performance"].update(
        total_return_pct=18.451, delta_vs_benchmark_pct=0.045, benchmark_return_pct=18.406
    )
    leaf = preview(owner, [message]).payload.turns[0]
    assert leaf.fact_bank.figures.model_dump(exclude_none=True) == result_display_figures(
        run.metrics
    )
    assert "run_id" not in leaf.fact_bank.model_dump()
    assert "result_card" not in leaf.fact_bank.result_card.model_dump()
    run.config_snapshot["template"] = "future_unknown_strategy"
    with pytest.raises(PublicExcerptSourceError):
        preview(owner, [message])


def test_deleted_or_foreign_conversation_refuses(owner):
    from argus.api.public_excerpts import EvidenceReceiptSourceMissingError

    _, message = add_pair(owner)
    api_state.store.conversation_owners[owner[1].id] = str(uuid4())
    with pytest.raises(EvidenceReceiptSourceMissingError):
        preview(owner, [message])
    api_state.store.conversation_owners[owner[1].id] = owner[0].id
    api_state.store.conversations[owner[1].id] = owner[1].model_copy(
        update={"deleted_at": utc(8)}
    )
    with pytest.raises(EvidenceReceiptSourceMissingError):
        preview(owner, [message])


@pytest.mark.parametrize("template", ["dca_accumulation", "rsi_mean_reversion"])
def test_non_buy_and_hold_freezes_complete_typed_configuration(owner, template):
    from copy import deepcopy

    from tests.public_excerpt_factories import (
        GENERATED_CARD_CONFIG_SNAPSHOT,
        INDICATOR_CONFIG_SNAPSHOT,
    )

    _, run, message = seed_backtest(owner)
    config = deepcopy(
        GENERATED_CARD_CONFIG_SNAPSHOT
        if template == "dca_accumulation"
        else INDICATOR_CONFIG_SNAPSHOT
    )
    run.config_snapshot.update(config)
    run.config_snapshot["date_range"] = {
        "start": "2024-01-02",
        "end": "2024-03-01",
        "display": "private source prose",
    }
    leaf = preview(owner, [message]).payload.turns[0]
    if template == "dca_accumulation":
        assert (
            leaf.fact_bank.config_snapshot.resolved_parameters.recurring_contribution
            == config["resolved_parameters"]["recurring_contribution"]
        )
    else:
        assert (
            leaf.fact_bank.config_snapshot.resolved_parameters.indicator_period
            == config["resolved_parameters"]["indicator_period"]
        )
    assert "private source prose" not in leaf.model_dump_json()
    run.config_snapshot = {"template": template}
    with pytest.raises(PublicExcerptSourceError):
        preview(owner, [message])


@pytest.mark.parametrize("series", [{"kind": "price"}, {"kind": "indicator"}, True])
def test_closed_rule_bank_refuses_incomplete_series_or_boolean_figures(owner, series):
    _, _, message = seed_backtest(owner)
    result = preview(owner, [message]).payload
    document = result.model_dump(mode="json")
    document["turns"][0]["fact_bank"]["config_snapshot"]["parameters"] = {
        "rule_spec": {
            "entry": {"conditions": [{"left": series, "operator": "gt", "right": 1}]}
        }
    }
    with pytest.raises(ValidationError):
        type(result).model_validate(document)


def test_guest_pending_sql_is_derived_from_the_same_closed_contract():
    from pathlib import Path

    from argus.domain.guest_pending_action_contract import (
        render_guest_pending_action_validator,
    )

    migration = Path(
        "supabase/migrations/20260909183646_share_answer_receipt_selections.sql"
    ).read_text()
    assert render_guest_pending_action_validator() in migration


@pytest.mark.parametrize("suffix", ["", "-preview", "-candidates"])
def test_disabled_selection_routes_do_not_advertise_via_slash_redirect(
    owner, monkeypatch, suffix
):
    from argus.api.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED", "false")
    client = TestClient(app, follow_redirects=False)
    response = client.get(f"/api/v1/conversations/{owner[1].id}/public-excerpt{suffix}/")
    assert response.status_code == 404
    assert response.content == client.get("/api/v1/absent-share-answer").content


def test_markdown_parentheses_in_a_listed_destination_are_preserved(owner):
    _, message = add_pair(owner, answer="[Report](https://apple.com/report_(2026))")
    message.metadata["research"]["sources"][0]["url"] = "https://apple.com/report_(2026)"
    assert preview(owner, [message]).payload.turns[0].answer == message.content
