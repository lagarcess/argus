"""Adversarial proofs for public evidence receipts.

These are attacks, not assertions. Each never-expose case poisons an artifact
with something on the section 3 list and requires that no receipt is produced,
rather than checking that a clean artifact happens to come out clean.
"""

from __future__ import annotations

from typing import Any, get_args

import pytest
from argus.api import state as api_state
from argus.api.public_excerpt_schemas import (
    PUBLIC_EXCERPT_OWNER_NOTE_MAX_LENGTH,
    PUBLIC_EXCERPT_ROBOTS_DIRECTIVE,
    PublicExcerptPayload,
    PublicExcerptView,
)
from argus.api.public_excerpts import (
    MemoryPublicExcerptRepository,
    create_receipt_for_artifact,
)
from argus.api.schemas import EvidenceArtifactType, User
from argus.domain.public_excerpts import (
    NEVER_EXPOSE_KEY_MARKERS,
    PublicExcerptOwnerNoteError,
    PublicExcerptSanitizationError,
    PublicExcerptSourceError,
    audit_public_excerpt_document,
    audit_public_excerpt_payload,
    build_public_excerpt_payload,
    new_public_excerpt_id,
    normalize_owner_note,
    payload_digest,
    snapshot_public_view,
)
from argus.domain.supabase_public_excerpts import (
    OWNER_COLUMNS,
    PUBLIC_VIEW_COLUMNS,
    TABLE,
    SupabasePublicExcerptMixin,
)
from pydantic import ValidationError

from tests.public_excerpt_factories import (
    ARTIFACT_ID,
    BUY_AND_HOLD_CONFIG_SNAPSHOT,
    BUY_THE_DIP_CONFIG_SNAPSHOT,
    CONVERSATION_ID,
    CROSSOVER_CONFIG_SNAPSHOT,
    CROSSOVER_DIFFERING_EXIT_CONFIG_SNAPSHOT,
    CROSSOVER_FOREIGN_EXIT_CONFIG_SNAPSHOT,
    DCA_CONFIG_SNAPSHOT,
    ENGINE_CONFIG_SNAPSHOT,
    GENERIC_RULE_SPEC_CONFIG_SNAPSHOT,
    IDEA_ID,
    IDEA_VERSION_ID,
    INDICATOR_CONFIG_SNAPSHOT,
    MACD_CONFIG_SNAPSHOT,
    RUN_ID,
    STRATEGY_ID,
    build_artifact,
    build_artifact_payload,
    build_chart,
    build_conversation,
    build_result_card,
    build_run,
    utc,
)

# The closed payload from spec section 2, spelled out so a silent addition fails.
CLOSED_PAYLOAD_FIELDS = {
    "schema_version",
    "idea_title",
    "asset_class",
    "symbols",
    "strategy_label",
    # Part of section 2's "strategy", not a new field: the label alone names a
    # category, so the defining parameters sit beside it.
    "strategy_facts",
    "assumptions",
    "date_range",
    "metrics",
    "benchmark_symbol",
    "benchmark_note",
    "visual",
    "owner_note",
    "content_language",
    "framing",
    "provenance_mark",
}

OWNER = User(
    id="99999999-9999-4999-8999-999999999999",
    email="owner@argus.test",
    username="owner",
    display_name="Owner",
    language="en",
    locale="en-US",
    theme="dark",
    is_admin=False,
    created_at=utc(),
    updated_at=utc(),
)

PRIVATE_IDS = (
    ARTIFACT_ID,
    CONVERSATION_ID,
    RUN_ID,
    IDEA_ID,
    IDEA_VERSION_ID,
    STRATEGY_ID,
)


def _payload(**overrides: Any) -> PublicExcerptPayload:
    kwargs: dict[str, Any] = {
        "artifact": build_artifact(),
        "run_chart": build_chart(),
        "run_config_snapshot": BUY_AND_HOLD_CONFIG_SNAPSHOT,
        "owner_note": None,
        "content_language": "en",
    }
    kwargs.update(overrides)
    return build_public_excerpt_payload(**kwargs)


# ── The closed payload ────────────────────────────────────────────────────────


def test_payload_carries_exactly_the_closed_section_two_fields() -> None:
    assert set(PublicExcerptPayload.model_fields) == CLOSED_PAYLOAD_FIELDS
    assert set(_payload().model_dump(mode="json")) == CLOSED_PAYLOAD_FIELDS


def test_payload_rejects_any_field_outside_the_closed_set() -> None:
    serialized = _payload().model_dump(mode="json")
    serialized["source_conversation_id"] = CONVERSATION_ID
    with pytest.raises(ValidationError):
        PublicExcerptPayload.model_validate(serialized)


def test_payload_is_frozen_after_construction() -> None:
    payload = _payload()
    with pytest.raises(ValidationError):
        payload.idea_title = "rewritten"


# ── Section 3: the never-expose list, attacked ────────────────────────────────


@pytest.mark.parametrize(
    ("case", "artifact_payload"),
    [
        (
            "source_conversation_id_in_prose",
            build_artifact_payload(
                result_card={
                    **build_result_card(),
                    "benchmark_note": f"See conversation {CONVERSATION_ID}",
                }
            ),
        ),
        (
            "source_run_id_in_metric_label",
            build_artifact_payload(
                result_card={
                    **build_result_card(),
                    "rows": [
                        {
                            "key": "total_return_pct",
                            "label": f"Total return for run {RUN_ID}",
                            "value": "+18.4%",
                        }
                    ],
                }
            ),
        ),
        (
            "route_receipt_in_assumptions",
            build_artifact_payload(
                result_card={
                    **build_result_card(),
                    "assumptions": ["route_receipt stage=interpret outcome=ready"],
                }
            ),
        ),
        (
            "provider_metadata_in_strategy_label",
            build_artifact_payload(
                result_card={
                    **build_result_card(),
                    "strategy_label": "Buy and hold via openrouter",
                }
            ),
        ),
        (
            "model_metadata_in_benchmark_note",
            build_artifact_payload(
                result_card={
                    **build_result_card(),
                    "benchmark_note": "Interpreted by langgraph then priced by alpaca",
                }
            ),
        ),
        (
            "raw_transcript_in_assumptions",
            build_artifact_payload(
                result_card={
                    **build_result_card(),
                    "assumptions": ["system_prompt: you are Argus"],
                }
            ),
        ),
        (
            "broker_token_in_metric_value",
            build_artifact_payload(
                result_card={
                    **build_result_card(),
                    "rows": [
                        {
                            "key": "total_return_pct",
                            "label": "Total return",
                            "value": "Bearer sk-live-abc",
                        }
                    ],
                }
            ),
        ),
        (
            "memory_record_id_in_note",
            build_artifact_payload(
                result_card={
                    **build_result_card(),
                    "benchmark_note": (
                        "Recalled from memory 77777777-7777-4777-8777-777777777777"
                    ),
                }
            ),
        ),
    ],
)
def test_never_expose_content_prevents_the_receipt_entirely(
    case: str, artifact_payload: dict[str, Any]
) -> None:
    with pytest.raises(PublicExcerptSanitizationError):
        _payload(artifact=build_artifact(payload=artifact_payload))


def test_a_poisoned_artifact_title_prevents_the_receipt() -> None:
    with pytest.raises(PublicExcerptSanitizationError):
        _payload(artifact=build_artifact(title=f"Run {RUN_ID}"))


def test_the_card_title_fallback_is_audited_too() -> None:
    # The card title is only read when the artifact title is empty, so it needs
    # its own case rather than riding on the artifact-title one.
    poisoned = build_artifact_payload(
        result_card={**build_result_card(), "title": f"Run {RUN_ID}"}
    )
    with pytest.raises(PublicExcerptSanitizationError):
        _payload(artifact=build_artifact(title="   ", payload=poisoned))


def test_clean_artifact_payload_never_leaks_a_private_id() -> None:
    serialized = _payload().model_dump_json()
    for private_id in PRIVATE_IDS:
        assert private_id not in serialized


@pytest.mark.parametrize(
    "smuggled_key",
    [
        "source_conversation_id",
        "route_receipts",
        "provider_name",
        "model_slug",
        "retry_payload",
        "raw_transcript",
        "broker_account",
        "memory_records",
        "auth_token",
    ],
)
def test_audit_rejects_a_key_named_after_never_expose_data(smuggled_key: str) -> None:
    # How a leak would actually arrive: a field added later that the schema does
    # not yet know about. The audit reads keys as well as values, at any depth.
    for marker in ("conversation_id", "route_receipt", "provider", "memory"):
        assert marker in NEVER_EXPOSE_KEY_MARKERS
    document = _payload().model_dump(mode="json")
    document["date_range"] = {**document["date_range"], smuggled_key: "anything"}
    with pytest.raises(PublicExcerptSanitizationError):
        audit_public_excerpt_document(document)


def test_audit_rejects_any_uuid_in_any_payload_value() -> None:
    payload = _payload()
    with pytest.raises(PublicExcerptSanitizationError):
        audit_public_excerpt_payload(
            payload.model_copy(
                update={"idea_title": "Idea 88888888-8888-4888-8888-888888888888"}
            )
        )


def test_owner_note_is_the_only_field_exempt_from_provider_word_matching() -> None:
    # The owner's own words are not Argus emitting provider metadata, so a note
    # mentioning a vendor is publishable. An identifier in it is not.
    payload = _payload(owner_note="I asked openrouter about this first")
    assert payload.owner_note == "I asked openrouter about this first"
    with pytest.raises(PublicExcerptSanitizationError):
        audit_public_excerpt_payload(
            payload.model_copy(update={"owner_note": CONVERSATION_ID}),
            private_ids=PRIVATE_IDS,
            skip_value_markers_for=("owner_note",),
        )


# ── The owner note, the one free-text channel ─────────────────────────────────


def test_owner_note_is_bounded() -> None:
    at_limit = ("note " * 60)[:PUBLIC_EXCERPT_OWNER_NOTE_MAX_LENGTH].strip()
    assert len(at_limit) <= PUBLIC_EXCERPT_OWNER_NOTE_MAX_LENGTH
    assert normalize_owner_note(at_limit) is not None
    over_limit = "note " * 100
    assert len(over_limit) > PUBLIC_EXCERPT_OWNER_NOTE_MAX_LENGTH
    with pytest.raises(PublicExcerptOwnerNoteError):
        normalize_owner_note(over_limit)


def test_owner_note_rejects_credential_shaped_tokens() -> None:
    with pytest.raises(PublicExcerptOwnerNoteError):
        normalize_owner_note("key EXAMPLENOTAREALCREDENTIALTOKEN")


def test_owner_note_collapses_control_characters_without_joining_words() -> None:
    assert normalize_owner_note("first\nsecond\t third") == "first second third"
    assert normalize_owner_note("  ") is None


# ── Immutability ──────────────────────────────────────────────────────────────


def test_rerunning_the_idea_does_not_move_the_frozen_numbers() -> None:
    artifact = build_artifact()
    first = _payload(artifact=artifact, run_chart=build_run().chart)
    first_digest = payload_digest(first)

    # The owner runs the same idea again: a new run, new numbers, new chart.
    rerun_card = build_result_card(total_return="+41.9%")
    rerun_artifact = build_artifact(
        payload=build_artifact_payload(result_card=rerun_card)
    )
    rerun = _payload(
        artifact=rerun_artifact,
        run_chart=build_chart(points=12, scale=3.0),
    )

    assert rerun.metrics[0].value == "+41.9%"
    assert first.metrics[0].value == "+18.4%"
    assert payload_digest(first) == first_digest
    assert payload_digest(rerun) != first_digest


def test_digest_is_stable_across_rebuilds_of_the_same_source() -> None:
    artifact = build_artifact()
    left = _payload(artifact=artifact)
    right = _payload(artifact=artifact)
    assert payload_digest(left) == payload_digest(right)


# ── Visual evidence ───────────────────────────────────────────────────────────


def test_visual_series_is_bounded_and_keeps_its_endpoints() -> None:
    dense = build_chart(points=1500)
    payload = _payload(run_chart=dense)
    assert payload.visual is not None
    assert len(payload.visual.series) <= 500
    assert payload.visual.series[0].time == dense["series"][0]["time"]
    assert payload.visual.series[-1].time == dense["series"][-1]["time"]


def test_receipt_renders_without_a_chart() -> None:
    payload = _payload(run_chart=None)
    assert payload.visual is None
    assert payload.metrics


def test_visual_never_carries_chart_markers_or_attribution() -> None:
    serialized = _payload().model_dump(mode="json")["visual"]
    assert set(serialized) == {"kind", "currency", "base_value", "series"}


# ── The public projection ─────────────────────────────────────────────────────


def _snapshot(**overrides: Any):
    from argus.api.public_excerpt_schemas import PublicExcerptSnapshot

    payload = overrides.pop("payload", None) or _payload()
    fields: dict[str, Any] = {
        "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "public_id": new_public_excerpt_id(),
        "owner_id": OWNER.id,
        "evidence_artifact_id": ARTIFACT_ID,
        "source_conversation_id": CONVERSATION_ID,
        "source_run_id": RUN_ID,
        "title": payload.idea_title,
        "payload": payload,
        "payload_digest": payload_digest(payload),
        "created_at": utc(),
    }
    fields.update(overrides)
    return PublicExcerptSnapshot.model_validate(fields)


def test_public_view_carries_no_owner_and_no_source_reference() -> None:
    serialized = snapshot_public_view(_snapshot()).model_dump(mode="json")
    assert set(serialized) == {
        "public_id",
        "status",
        "indexing",
        "created_at",
        "payload",
    }
    body = str(serialized)
    for private_id in (OWNER.id, *PRIVATE_IDS):
        assert private_id not in body


def test_revoked_view_keeps_nothing_from_the_payload() -> None:
    view = snapshot_public_view(_snapshot(revoked_at=utc(5), revocation_reason="owner_revoked"))
    assert view.status == "revoked"
    assert view.payload is None
    assert view.created_at is None


def test_noindex_is_a_constant_with_no_alternative_value() -> None:
    assert PUBLIC_EXCERPT_ROBOTS_DIRECTIVE == "noindex, nofollow"
    assert snapshot_public_view(_snapshot()).indexing == PUBLIC_EXCERPT_ROBOTS_DIRECTIVE
    with pytest.raises(ValidationError):
        PublicExcerptView(public_id="abc", status="available", indexing="index, follow")


# ── Construction proof for the public read path ───────────────────────────────


class _RecordingQuery:
    def __init__(self, log: dict[str, Any], rows: list[dict[str, Any]]) -> None:
        self._log = log
        self._rows = rows

    def select(self, columns: str) -> _RecordingQuery:
        self._log["selects"].append(columns)
        return self

    def eq(self, column: str, value: Any) -> _RecordingQuery:
        self._log["filters"].append((column, value))
        return self

    def is_(self, column: str, value: Any) -> _RecordingQuery:
        self._log["filters"].append((column, value))
        return self

    def limit(self, count: int) -> _RecordingQuery:
        return self

    def order(self, column: str, desc: bool = False) -> _RecordingQuery:
        return self

    def execute(self) -> Any:
        class _Result:
            data = self._rows

        return _Result()


class _RecordingClient:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.log: dict[str, Any] = {"tables": [], "selects": [], "filters": [], "rpc": []}
        self._rows = rows or []

    def table(self, name: str) -> _RecordingQuery:
        self.log["tables"].append(name)
        return _RecordingQuery(self.log, self._rows)

    def rpc(self, name: str, params: dict[str, Any]) -> Any:
        self.log["rpc"].append(name)
        raise AssertionError("The public read must not call an RPC.")


class _Gateway(SupabasePublicExcerptMixin):
    def __init__(self, client: _RecordingClient) -> None:
        self.client = client


def test_public_read_touches_one_table_with_a_fixed_column_list() -> None:
    payload = _payload()
    client = _RecordingClient(
        rows=[
            {
                "public_id": "abcdefghijklmnopqrstuvwx",
                "payload": payload.model_dump(mode="json"),
                "created_at": utc().isoformat(),
                "revoked_at": None,
            }
        ]
    )
    view = _Gateway(client).read_public_excerpt_view(public_id="abcdefghijklmnopqrstuvwx")

    assert view.status == "available"
    assert client.log["tables"] == [TABLE]
    assert client.log["selects"] == [",".join(PUBLIC_VIEW_COLUMNS)]
    assert client.log["filters"] == [("public_id", "abcdefghijklmnopqrstuvwx")]
    assert client.log["rpc"] == []


def test_public_read_column_list_excludes_every_ownership_reference() -> None:
    assert PUBLIC_VIEW_COLUMNS == ("public_id", "payload", "created_at", "revoked_at")
    forbidden = {
        "owner_id",
        "evidence_artifact_id",
        "source_conversation_id",
        "source_run_id",
        "title",
        "payload_digest",
        "revocation_reason",
    }
    assert forbidden.isdisjoint(PUBLIC_VIEW_COLUMNS)
    assert forbidden.issubset(set(OWNER_COLUMNS))


def test_unknown_public_id_answers_a_tombstone_rather_than_an_oracle() -> None:
    client = _RecordingClient(rows=[])
    view = _Gateway(client).read_public_excerpt_view(public_id="unknown-public-id-xxxx")
    assert view.status == "revoked"
    assert view.payload is None


# ── Source guards ─────────────────────────────────────────────────────────────


def test_results_only_is_enforced_by_the_artifact_type_itself() -> None:
    # Section 7.5: completed backtest results only. Comparisons and research
    # answers cannot even be represented as a shareable artifact today.
    assert get_args(EvidenceArtifactType) == ("backtest",)


def test_a_non_backtest_artifact_is_refused_at_runtime_too() -> None:
    # Bypasses validation the way a raw database row could, so the guard is not
    # resting entirely on the type annotation above.
    artifact = build_artifact().model_copy()
    object.__setattr__(artifact, "artifact_type", "comparison")
    with pytest.raises(PublicExcerptSourceError):
        _payload(artifact=artifact)


def test_a_result_without_a_tested_window_is_not_shareable() -> None:
    card = build_result_card()
    card.pop("date_range")
    with pytest.raises(PublicExcerptSourceError):
        _payload(artifact=build_artifact(payload=build_artifact_payload(result_card=card)))


# ── Memory-mode repository parity ─────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _memory_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    api_state.store.reset()


def _seed_owned_result() -> None:
    artifact = build_artifact()
    run = build_run()
    # The conversation is part of the fixture because an artifact whose source is
    # gone is no longer shareable.
    conversation = build_conversation()
    api_state.store.users[OWNER.id] = OWNER
    api_state.store.conversations[conversation.id] = conversation
    api_state.store.conversation_owners[conversation.id] = OWNER.id
    api_state.store.evidence_artifacts[artifact.id] = artifact
    api_state.store.evidence_artifact_owners[artifact.id] = OWNER.id
    api_state.store.backtest_runs[run.id] = run
    api_state.store.backtest_run_owners[run.id] = OWNER.id


def test_creating_twice_returns_the_same_live_receipt() -> None:
    _seed_owned_result()
    first, first_created = create_receipt_for_artifact(
        user=OWNER, artifact_id=ARTIFACT_ID, owner_note=None
    )
    second, second_created = create_receipt_for_artifact(
        user=OWNER, artifact_id=ARTIFACT_ID, owner_note=None
    )
    assert first.public_id == second.public_id
    # Only the first call created anything, which is what the funnel counts.
    assert (first_created, second_created) == (True, False)


def test_revocation_takes_effect_on_the_next_public_read() -> None:
    _seed_owned_result()
    snapshot, _ = create_receipt_for_artifact(
        user=OWNER, artifact_id=ARTIFACT_ID, owner_note=None
    )
    repository = MemoryPublicExcerptRepository(api_state.store)
    assert repository.read_public_excerpt_view(public_id=snapshot.public_id).status == (
        "available"
    )

    repository.revoke_public_excerpt_snapshot(
        owner_id=OWNER.id, snapshot_id=snapshot.id
    )

    view = repository.read_public_excerpt_view(public_id=snapshot.public_id)
    assert view.status == "revoked"
    assert view.payload is None


def test_revocation_is_one_way() -> None:
    _seed_owned_result()
    snapshot, _ = create_receipt_for_artifact(
        user=OWNER, artifact_id=ARTIFACT_ID, owner_note=None
    )
    repository = MemoryPublicExcerptRepository(api_state.store)
    revoked, revoked_now = repository.revoke_public_excerpt_snapshot(
        owner_id=OWNER.id, snapshot_id=snapshot.id
    )
    again, again_now = repository.revoke_public_excerpt_snapshot(
        owner_id=OWNER.id, snapshot_id=snapshot.id
    )
    assert revoked is not None and again is not None
    assert again.revoked_at == revoked.revoked_at
    assert again.revocation_reason == "owner_revoked"
    # Only the transition is a revocation; the retry is the same outcome.
    assert (revoked_now, again_now) == (True, False)


def test_another_account_cannot_read_or_revoke_a_receipt() -> None:
    _seed_owned_result()
    snapshot, _ = create_receipt_for_artifact(
        user=OWNER, artifact_id=ARTIFACT_ID, owner_note=None
    )
    repository = MemoryPublicExcerptRepository(api_state.store)
    stranger = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    assert (
        repository.get_owned_public_excerpt_snapshot(
            owner_id=stranger, snapshot_id=snapshot.id
        )
        is None
    )
    assert repository.revoke_public_excerpt_snapshot(
        owner_id=stranger, snapshot_id=snapshot.id
    ) == (None, False)
    assert repository.list_public_excerpt_snapshots(owner_id=stranger) == []


def test_public_id_is_unguessable_and_distinct_per_receipt() -> None:
    ids = {new_public_excerpt_id() for _ in range(500)}
    assert len(ids) == 500
    assert all(len(value) >= 22 for value in ids)


# ── The strategy a receipt claims to show ─────────────────────────────────────


def test_an_indicator_receipt_freezes_the_rules_that_produced_it() -> None:
    """The label names a category; these are the parameters that decided the trade.

    Without them two RSI runs with different periods and thresholds render as the
    same strategy with different numbers, which is the opposite of evidence.
    """
    payload = _payload(run_config_snapshot=INDICATOR_CONFIG_SNAPSHOT)
    facts = {fact.key: fact.value for fact in payload.strategy_facts}
    assert facts["indicator"] == "RSI"
    assert facts["indicator_period"] == "14"
    assert facts["entry_threshold"] == "30"
    assert facts["exit_threshold"] == "70"
    # Direction is deliberately absent: Argus is long only, so a frozen "below"
    # names which way the indicator moved and not a position taken.
    assert "direction" not in facts


def test_two_indicator_runs_with_different_rules_do_not_look_identical() -> None:
    tighter = {
        **INDICATOR_CONFIG_SNAPSHOT,
        "resolved_parameters": {
            **INDICATOR_CONFIG_SNAPSHOT["resolved_parameters"],
            "indicator_period": 7,
            "entry_threshold": 20,
        },
    }
    first = _payload(run_config_snapshot=INDICATOR_CONFIG_SNAPSHOT)
    second = _payload(run_config_snapshot=tighter)
    assert first.strategy_facts != second.strategy_facts
    assert payload_digest(first) != payload_digest(second)


def test_a_recurring_buy_receipt_freezes_its_cadence() -> None:
    payload = _payload(run_config_snapshot=DCA_CONFIG_SNAPSHOT)
    facts = {fact.key: fact.value for fact in payload.strategy_facts}
    assert facts["cadence"] == "monthly"
    assert facts["strategy_type"] == "dca accumulation"


def test_buy_and_hold_stays_simple_rather_than_inventing_facts() -> None:
    payload = _payload(run_config_snapshot=BUY_AND_HOLD_CONFIG_SNAPSHOT)
    assert [fact.key for fact in payload.strategy_facts] == ["strategy_type"]


def test_a_crossover_receipt_freezes_both_of_its_windows() -> None:
    """The defect this closes: a crossover described by one generic period.

    fast and slow are what decide the trades, and a 20/50 crossover and a 5/200
    crossover are different strategies that would otherwise render identically.
    """
    payload = _payload(run_config_snapshot=CROSSOVER_CONFIG_SNAPSHOT)
    facts = {fact.key: fact.value for fact in payload.strategy_facts}
    assert facts["fast_indicator"] == "sma"
    assert facts["fast_period"] == "20"
    assert facts["slow_indicator"] == "sma"
    assert facts["slow_period"] == "50"
    assert "direction" not in facts
    # Named for what ran, not for the execution type that carried it.
    assert facts["strategy_type"] == "moving average crossover"


def test_two_crossovers_with_different_windows_do_not_look_identical() -> None:
    faster = {
        **CROSSOVER_CONFIG_SNAPSHOT,
        "resolved_strategy": {
            **CROSSOVER_CONFIG_SNAPSHOT["resolved_strategy"],
            "entry_rule": {
                **CROSSOVER_CONFIG_SNAPSHOT["resolved_strategy"]["entry_rule"],
                "fast_period": 5,
                "slow_period": 200,
            },
        },
    }
    first = _payload(run_config_snapshot=CROSSOVER_CONFIG_SNAPSHOT)
    second = _payload(run_config_snapshot=faster)
    assert first.strategy_facts != second.strategy_facts
    assert payload_digest(first) != payload_digest(second)


def test_a_crossover_missing_one_window_refuses_to_publish() -> None:
    """Half a crossover is not a truthful record of a crossover."""
    half = {
        **CROSSOVER_CONFIG_SNAPSHOT,
        "resolved_strategy": {
            **CROSSOVER_CONFIG_SNAPSHOT["resolved_strategy"],
            "entry_rule": {
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 20,
            },
        },
    }
    with pytest.raises(PublicExcerptSourceError):
        _payload(run_config_snapshot=half)


def test_a_macd_receipt_freezes_all_three_of_its_periods() -> None:
    payload = _payload(run_config_snapshot=MACD_CONFIG_SNAPSHOT)
    facts = {fact.key: fact.value for fact in payload.strategy_facts}
    assert facts["fast_period"] == "12"
    assert facts["slow_period"] == "26"
    assert facts["signal_period"] == "9"
    assert facts["strategy_type"] == "macd crossover"


def test_buy_the_dip_borrows_no_parameters_from_its_execution_type() -> None:
    """Its trigger is hardcoded in the engine, so there is nothing frozen to show.

    It shares indicator_threshold as an execution type, so the risk is showing an
    indicator and thresholds that belong to a different strategy.
    """
    payload = _payload(run_config_snapshot=BUY_THE_DIP_CONFIG_SNAPSHOT)
    assert [fact.key for fact in payload.strategy_facts] == ["strategy_type"]
    assert payload.strategy_facts[0].value == "buy the dip"


def test_a_run_configured_through_the_engine_path_still_describes_itself() -> None:
    """The direct path stores the engine config, with parameters and no resolved_*."""
    payload = _payload(run_config_snapshot=ENGINE_CONFIG_SNAPSHOT)
    facts = {fact.key: fact.value for fact in payload.strategy_facts}
    assert facts["cadence"] == "weekly"


def test_a_generic_rule_spec_refuses_rather_than_publishing_a_generic_label() -> None:
    """A condition tree cannot round-trip into flat facts, so it is not shareable.

    Returning no facts and letting creation continue published a page that named a
    strategy this module had declined to describe, which is the failure mode a receipt
    exists to prevent.
    """
    with pytest.raises(PublicExcerptSourceError):
        _payload(run_config_snapshot=GENERIC_RULE_SPEC_CONFIG_SNAPSHOT)


def test_a_run_with_no_config_refuses_rather_than_publishing() -> None:
    """No frozen configuration means no way to state what ran."""
    with pytest.raises(PublicExcerptSourceError):
        _payload(run_config_snapshot=None)


def test_strategy_facts_carry_only_readable_scalars() -> None:
    """A nested structure is not a fact a viewer can read, and could hide anything."""
    hostile = {
        "resolved_parameters": {
            "indicator": {"nested": "structure"},
            "indicator_period": [1, 2, 3],
            "entry_threshold": True,
        },
        "resolved_strategy": {"strategy_type": "indicator_threshold"},
    }
    # Fails closed rather than keeping the name of a strategy whose parameters it
    # could not read.
    with pytest.raises(PublicExcerptSourceError):
        _payload(run_config_snapshot=hostile)


def test_strategy_facts_are_audited_like_the_rest_of_the_payload() -> None:
    # A complete shape, so the poisoned value is actually projected and has to be
    # caught by the audit rather than dropped for being incomplete.
    poisoned = {
        **INDICATOR_CONFIG_SNAPSHOT,
        "resolved_parameters": {
            **INDICATOR_CONFIG_SNAPSHOT["resolved_parameters"],
            "indicator": f"RSI via openrouter {CONVERSATION_ID}",
        },
    }
    with pytest.raises(PublicExcerptSanitizationError):
        _payload(run_config_snapshot=poisoned)


def test_every_executable_strategy_shape_round_trips_completely() -> None:
    """The enumeration itself, driven from the capability registry.

    A hand-picked field list is the defect this closes, so the guard is not a
    hand-kept list either: it walks every template the registry calls executable and
    requires a fixture and a complete projection for each. Adding a strategy, or a
    parameter to one, fails here instead of shipping a receipt that describes a run
    that never happened.
    """
    from argus.domain.capability_registry import EXECUTABLE_TEMPLATES
    from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

    # Every executable template, the snapshot a run of it freezes, and the facts a
    # receipt must show. Buy and hold and buy the dip declare no tunable parameters.
    coverage: dict[str, tuple[dict[str, Any], set[str]]] = {
        "buy_and_hold": (BUY_AND_HOLD_CONFIG_SNAPSHOT, set()),
        "buy_the_dip": (BUY_THE_DIP_CONFIG_SNAPSHOT, set()),
        "rsi_mean_reversion": (
            INDICATOR_CONFIG_SNAPSHOT,
            {"indicator", "indicator_period", "entry_threshold", "exit_threshold"},
        ),
        "moving_average_crossover": (
            CROSSOVER_CONFIG_SNAPSHOT,
            {"fast_indicator", "fast_period", "slow_indicator", "slow_period"},
        ),
        "dca_accumulation": (DCA_CONFIG_SNAPSHOT, {"cadence"}),
    }
    assert set(coverage) == set(EXECUTABLE_TEMPLATES), (
        "an executable strategy has no receipt projection: "
        f"{sorted(set(EXECUTABLE_TEMPLATES) ^ set(coverage))}"
    )

    for template, (snapshot, expected) in coverage.items():
        facts = {
            fact.key: fact.value
            for fact in _payload(run_config_snapshot=snapshot).strategy_facts
        }
        assert facts, f"{template} produced a receipt describing no strategy"
        assert "strategy_type" in facts, f"{template} receipt names no strategy"
        assert expected <= set(facts), (
            f"{template} receipt is missing {sorted(expected - set(facts))}"
        )
        # Every parameter the registry declares tunable is disclosed, so a receipt
        # cannot omit one that changed the result.
        declared = set(STRATEGY_CAPABILITIES[template].parameters)
        undisclosed = {
            key
            for key in declared
            if key not in facts and key.replace("dca_", "") not in facts
        }
        assert not undisclosed, f"{template} hides tunable {sorted(undisclosed)}"


def test_draft_strategies_cannot_reach_a_receipt_at_all() -> None:
    """A draft template has no execution type, so it can never produce a run."""
    from argus.domain.capability_registry import EXECUTABLE_TEMPLATES
    from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

    for template, capability in STRATEGY_CAPABILITIES.items():
        if template in EXECUTABLE_TEMPLATES:
            continue
        assert capability.execution_strategy_type is None


# ── Fail closed: complete strategy facts, or no receipt ───────────────────────


def test_an_unsupported_strategy_shape_refuses_instead_of_publishing() -> None:
    """The guard that keeps this class closed.

    A shape nobody has taught the projection is unknown by definition, so it cannot be
    described faithfully. Refusing is the only honest outcome, and it is what makes a
    future strategy a refusal rather than a page that misstates what ran.
    """
    unknown = {
        "template": "some_strategy_invented_next_quarter",
        "resolved_strategy": {"strategy_type": "some_strategy_invented_next_quarter"},
        "resolved_parameters": {"timeframe": "1D"},
    }
    with pytest.raises(PublicExcerptSourceError):
        _payload(run_config_snapshot=unknown)


def test_the_refusal_reaches_the_owner_as_a_readable_reason() -> None:
    """A refusal the owner cannot read is a dead end, so the message says what to do."""
    with pytest.raises(PublicExcerptSourceError) as caught:
        _payload(run_config_snapshot=GENERIC_RULE_SPEC_CONFIG_SNAPSHOT)
    message = str(caught.value)
    assert "cannot be shared" in message
    # Owner-facing copy, so no internals and no jargon from the runtime.
    for internal in ("rule_spec", "config_snapshot", "strategy_facts", "projection"):
        assert internal not in message


def test_a_crossover_that_exits_on_other_windows_states_both_sides() -> None:
    """The defect: the exit side was read from the entry rule, so it could be wrong.

    Entry and exit are compiled independently, so a receipt that reports only the entry
    windows can state an exit that never ran.
    """
    payload = _payload(run_config_snapshot=CROSSOVER_DIFFERING_EXIT_CONFIG_SNAPSHOT)
    facts = {fact.key: fact.value for fact in payload.strategy_facts}
    assert facts["fast_indicator"] == "sma"
    assert facts["fast_period"] == "20"
    assert facts["slow_period"] == "50"
    # Taken from the exit rule, not inherited from the entry rule.
    assert facts["exit_fast_indicator"] == "ema"
    assert facts["exit_fast_period"] == "9"
    assert facts["exit_slow_indicator"] == "ema"
    assert facts["exit_slow_period"] == "21"


def test_a_matching_exit_adds_no_redundant_facts() -> None:
    """When the exit repeats the entry's windows there is nothing extra to say."""
    facts = {
        fact.key
        for fact in _payload(run_config_snapshot=CROSSOVER_CONFIG_SNAPSHOT).strategy_facts
    }
    assert not any(key.startswith("exit_") for key in facts)


def test_a_crossover_with_a_foreign_exit_rule_refuses() -> None:
    """A crossover entry with a MACD exit is a shape with no faithful projection."""
    with pytest.raises(PublicExcerptSourceError):
        _payload(run_config_snapshot=CROSSOVER_FOREIGN_EXIT_CONFIG_SNAPSHOT)


def test_no_publishable_payload_ever_carries_an_empty_strategy_block() -> None:
    """The class-level invariant, asserted over every shape a fixture can build.

    Any snapshot either yields a named strategy with its defining parameters, or raises.
    There is no third outcome, which is what stops a partial or absent block reaching a
    public page.
    """
    snapshots = [
        BUY_AND_HOLD_CONFIG_SNAPSHOT,
        BUY_THE_DIP_CONFIG_SNAPSHOT,
        INDICATOR_CONFIG_SNAPSHOT,
        CROSSOVER_CONFIG_SNAPSHOT,
        CROSSOVER_DIFFERING_EXIT_CONFIG_SNAPSHOT,
        CROSSOVER_FOREIGN_EXIT_CONFIG_SNAPSHOT,
        MACD_CONFIG_SNAPSHOT,
        DCA_CONFIG_SNAPSHOT,
        ENGINE_CONFIG_SNAPSHOT,
        GENERIC_RULE_SPEC_CONFIG_SNAPSHOT,
        None,
        {},
        {"template": "buy_and_hold"},
        {"resolved_strategy": {"strategy_type": "signal_strategy"}},
    ]
    for snapshot in snapshots:
        try:
            payload = _payload(run_config_snapshot=snapshot)
        except PublicExcerptSourceError:
            continue
        keys = [fact.key for fact in payload.strategy_facts]
        assert keys, f"published with no strategy facts: {snapshot}"
        assert keys[0] == "strategy_type", f"published unnamed strategy: {snapshot}"


def test_a_differing_exit_is_covered_by_the_registry_walk_too() -> None:
    """The registry names one crossover; the compiler admits two variants of it.

    The walk above proves the matching-exit variant. This proves the other one, so
    neither reading of "moving_average_crossover" is left unchecked.
    """
    facts = {
        fact.key: fact.value
        for fact in _payload(
            run_config_snapshot=CROSSOVER_DIFFERING_EXIT_CONFIG_SNAPSHOT
        ).strategy_facts
    }
    for key in ("fast_indicator", "fast_period", "slow_indicator", "slow_period"):
        assert key in facts
        assert f"exit_{key}" in facts


def test_no_shape_publishes_a_direction() -> None:
    """Argus executes long only, so direction cannot be published at all.

    ``_build_long_only_execution_ledger`` is the whole execution path, so a frozen
    "bearish" describes which way two averages crossed, never a short position. On a
    public page beside a sell rule it reads as shorting a stock, which is a capability
    Argus does not have. The rendered sentence carries the crossing direction instead.
    """
    from argus.api.public_excerpt_schemas import StrategyFactKey

    assert "direction" not in get_args(StrategyFactKey)
    for snapshot in (
        INDICATOR_CONFIG_SNAPSHOT,
        CROSSOVER_CONFIG_SNAPSHOT,
        CROSSOVER_DIFFERING_EXIT_CONFIG_SNAPSHOT,
        MACD_CONFIG_SNAPSHOT,
        DCA_CONFIG_SNAPSHOT,
        BUY_AND_HOLD_CONFIG_SNAPSHOT,
        BUY_THE_DIP_CONFIG_SNAPSHOT,
    ):
        payload = _payload(run_config_snapshot=snapshot)
        keys = {fact.key for fact in payload.strategy_facts}
        assert "direction" not in keys, snapshot.get("template")
        # And nothing in the payload spells it out in prose either.
        assert "bearish" not in payload.model_dump_json().lower()


# ── The two classes, closed by invariant rather than by case ──────────────────


def test_no_field_of_a_crossover_rule_can_change_silently() -> None:
    """The guard for the strategy class, at the altitude the class lives at.

    Three rounds each fixed one field of a crossover rule and compared only the fields
    already known: entry-only, then windows, then direction. The compiler consumes the
    rule whole, so the invariant is stated over its whole field set instead. Mutating
    any field the engine reads must either change what the receipt says or refuse it.
    Silently producing the mirrored receipt for a rule that is not the mirror is the
    defect, whichever field carries it.
    """
    from argus.domain.public_excerpts import CROSSOVER_RULE_FIELDS

    baseline = _payload(run_config_snapshot=CROSSOVER_CONFIG_SNAPSHOT).strategy_facts
    entry = CROSSOVER_CONFIG_SNAPSHOT["resolved_strategy"]["entry_rule"]
    mutations: dict[str, object] = {
        "type": "macd_crossover",
        "fast_indicator": "ema",
        "fast_period": 7,
        "slow_indicator": "ema",
        "slow_period": 200,
        # The mirror of a bullish entry is bearish, so bullish is a real difference.
        "direction": "bullish",
    }
    assert set(mutations) == set(CROSSOVER_RULE_FIELDS), (
        "a field the engine reads has no mutation case: "
        f"{sorted(set(CROSSOVER_RULE_FIELDS) ^ set(mutations))}"
    )

    for field, value in mutations.items():
        snapshot = {
            **CROSSOVER_CONFIG_SNAPSHOT,
            "resolved_strategy": {
                **CROSSOVER_CONFIG_SNAPSHOT["resolved_strategy"],
                "exit_rule": {**entry, "direction": "bearish", field: value},
            },
        }
        try:
            facts = _payload(run_config_snapshot=snapshot).strategy_facts
        except PublicExcerptSourceError:
            continue
        assert facts != baseline, (
            f"changing exit_rule[{field!r}] produced the mirrored receipt unchanged, "
            "so the page states an exit that did not run"
        )


def test_an_exit_configured_like_the_entry_refuses() -> None:
    """The third instance itself, kept as a case beside the invariant.

    A bullish entry with a bullish exit compiles to cross_above on both sides, so the
    mirrored sentence, sold when it crossed back below, would describe the opposite of
    what ran. Direction is not publishable on a long-only surface, so this refuses.
    """
    entry = CROSSOVER_CONFIG_SNAPSHOT["resolved_strategy"]["entry_rule"]
    same_direction = {
        **CROSSOVER_CONFIG_SNAPSHOT,
        "resolved_strategy": {
            **CROSSOVER_CONFIG_SNAPSHOT["resolved_strategy"],
            "exit_rule": {**entry, "direction": "bullish"},
        },
    }
    with pytest.raises(PublicExcerptSourceError):
        _payload(run_config_snapshot=same_direction)


def test_the_mirror_is_the_engine_s_own_not_a_second_opinion() -> None:
    """A restated mirror could drift from the engine's. This borrows it instead."""
    from argus.domain import public_excerpts
    from argus.domain.backtesting.rules.signals import (
        _opposite_moving_average_crossover_rule,
    )

    assert (
        public_excerpts.engine_mirrored_exit_rule
        is _opposite_moving_average_crossover_rule
    )

