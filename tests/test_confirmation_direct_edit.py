"""Direct capital/date edits on a pending confirmation: the no-turn drawer path.

Covers the §3.4 contract: a direct edit spends no turn, creates no job,
produces no backtest row, obeys the same validation and coverage gates as a
conversational edit, and produces the identical canonical artifact.
"""

from __future__ import annotations

from typing import Any

from argus.api.chat.confirmation import runtime_confirmation_card
from argus.api.main import app
from argus.api.message_store import create_message
from fastapi.testclient import TestClient

CONFIRMATION_ID = "22222222-2222-4222-8222-222222222222"


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    return client


def _conversation(client: TestClient) -> dict[str, Any]:
    return client.post("/api/v1/conversations", json={}).json()["conversation"]


def _mock_user_id(client: TestClient) -> str:
    return client.get("/api/v1/me").json()["user"]["id"]


def _confirmation_payload(
    *,
    strategy_type: str = "buy_and_hold",
    cadence: str | None = None,
    capital: float = 10000,
) -> dict[str, Any]:
    strategy: dict[str, Any] = {
        "strategy_type": strategy_type,
        "asset_universe": ["NFLX"],
        "asset_class": "equity",
        "timeframe": "1D",
        "date_range": {"start": "2023-01-02", "end": "2023-06-30"},
        "sizing_mode": "capital_amount",
        "capital_amount": capital,
        "extra_parameters": {
            "date_range_raw_text": "first half of 2023",
            "evidence_spans": {"date_range": "first half of 2023"},
        },
    }
    launch: dict[str, Any] = {
        "strategy_type": strategy_type,
        "symbol": "NFLX",
        "symbols": ["NFLX"],
        "asset_class": "equity",
        "timeframe": "1D",
        "date_range": {"start": "2023-01-02", "end": "2023-06-30"},
        "sizing_mode": "capital_amount",
        "capital_amount": capital,
        "parameters": {},
        "risk_rules": [],
        "benchmark_symbol": "SPY",
        "language": "en",
    }
    if cadence is not None:
        strategy["cadence"] = cadence
        launch["cadence"] = cadence
    return {
        "confirmation_id": CONFIRMATION_ID,
        "artifact_id": CONFIRMATION_ID,
        "strategy": strategy,
        "optional_parameters": {},
        "launch_payload": launch,
        "validation": {"status": "ready_to_run", "executable": True},
    }


def _plant_confirmation(
    client: TestClient,
    conversation_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or _confirmation_payload()
    card = runtime_confirmation_card(
        {"stage_outcome": "await_approval", "confirmation_payload": payload},
        confirmation_id=str(payload["confirmation_id"]),
        conversation_id=conversation_id,
        language="en",
    )
    assert card is not None
    metadata: dict[str, Any] = {
        "conversation_mode": "confirm",
        "confirmation_card": card,
        "confirmation_payload": payload,
    }
    create_message(
        user_id=_mock_user_id(client),
        conversation_id=conversation_id,
        role="assistant",
        content=str(card.get("summary") or ""),
        metadata=metadata,
        settle_usage=None,
    )
    return metadata


def _direct_edit(
    client: TestClient,
    conversation_id: str,
    confirmation_id: str,
    body: dict[str, Any],
):
    return client.post(
        f"/api/v1/conversations/{conversation_id}/confirmations/"
        f"{confirmation_id}/direct-edit",
        json=body,
    )


def _conversation_messages(client: TestClient, conversation_id: str) -> list[dict]:
    return client.get(f"/api/v1/conversations/{conversation_id}/messages").json()["items"]


def test_capital_edit_updates_in_place_without_spending_a_turn() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    usage_before = client.get("/api/v1/me/usage").json()
    messages_before = _conversation_messages(client, conversation["id"])

    response = _direct_edit(
        client,
        conversation["id"],
        CONFIRMATION_ID,
        {"capital": 25000},
    )
    assert response.status_code == 200, response.text
    message = response.json()["message"]
    card = message["metadata"]["confirmation_card"]
    # In place means in place: same card, edited. Nothing is spent, so
    # nothing new appears and the card keeps its identity.
    assert card["confirmation_id"] == CONFIRMATION_ID
    assert card["confirmation_state"] == "active"
    capital_rows = [row for row in card["rows"] if row["key"] == "starting_capital"]
    assert capital_rows and capital_rows[0]["value"] == "$25,000"
    payload = message["metadata"]["confirmation_payload"]
    assert payload["confirmation_id"] == CONFIRMATION_ID
    assert payload["launch_payload"]["capital_amount"] == 25000
    assert payload["strategy"]["capital_amount"] == 25000
    provenance = payload["strategy"]["extra_parameters"]["field_provenance"]
    assert provenance["capital_amount"] == "starting_capital"

    messages_after = _conversation_messages(client, conversation["id"])
    assert len(messages_after) == len(
        messages_before
    ), "an in-place edit must not mint a new message"
    assert message["id"] in {
        item["id"] for item in messages_before
    }, "the edit must land on the existing card message"
    stored = next(item for item in messages_after if item["id"] == message["id"])
    assert (
        stored["metadata"]["confirmation_payload"]["strategy"]["capital_amount"] == 25000
    ), "the stored record is the edited card, not a copy"

    usage_after = client.get("/api/v1/me/usage").json()
    assert usage_after == usage_before, "a direct edit must not spend any allowance"
    run_items = [
        item
        for item in client.get("/api/v1/history").json()["items"]
        if item["type"] == "run"
    ]
    assert run_items == [], "a direct edit must not create a backtest row"


def test_date_edit_updates_window_and_drops_stale_prose_evidence() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])

    response = _direct_edit(
        client,
        conversation["id"],
        CONFIRMATION_ID,
        {"date_window": {"start": "2023-02-01", "end": "2023-05-31"}},
    )
    assert response.status_code == 200, response.text
    payload = response.json()["message"]["metadata"]["confirmation_payload"]
    assert payload["launch_payload"]["date_range"] == {
        "start": "2023-02-01",
        "end": "2023-05-31",
    }
    strategy = payload["strategy"]
    assert strategy["date_range"] == {"start": "2023-02-01", "end": "2023-05-31"}
    extra = strategy["extra_parameters"]
    assert "date_range_raw_text" not in extra
    assert "date_range" not in (extra.get("evidence_spans") or {})
    intent = extra["date_range_intent"]
    assert intent["kind"] == "explicit_range"
    assert strategy["extra_parameters"]["field_provenance"]["date_range"] == (
        "explicit_user"
    )


def test_compound_capital_and_date_edit_applies_both() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])

    response = _direct_edit(
        client,
        conversation["id"],
        CONFIRMATION_ID,
        {"capital": 5000, "date_window": {"start": "2023-03-01", "end": "2023-06-30"}},
    )
    assert response.status_code == 200, response.text
    payload = response.json()["message"]["metadata"]["confirmation_payload"]
    assert payload["launch_payload"]["capital_amount"] == 5000
    assert payload["launch_payload"]["date_range"]["start"] == "2023-03-01"


def test_dca_capital_edit_sets_the_recurring_contribution_role() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(
        client,
        conversation["id"],
        _confirmation_payload(strategy_type="dca_accumulation", cadence="weekly"),
    )

    # A recurring contribution is exempt from the bankroll floor (the launch
    # adapter's rule), so an ordinary small DCA amount stays valid here.
    response = _direct_edit(
        client,
        conversation["id"],
        CONFIRMATION_ID,
        {"capital": 250},
    )
    assert response.status_code == 200, response.text
    message = response.json()["message"]
    payload = message["metadata"]["confirmation_payload"]
    strategy = payload["strategy"]
    assert strategy["capital_amount"] == 250
    assert strategy["extra_parameters"]["recurring_contribution"] == 250
    provenance = strategy["extra_parameters"]["field_provenance"]
    assert provenance["capital_amount"] == "recurring_contribution"
    card = message["metadata"]["confirmation_card"]
    contribution_rows = [row for row in card["rows"] if row["key"] == "contribution"]
    assert contribution_rows and contribution_rows[0]["value"] == "$250"
    constraints = card["capabilities"]["edit_constraints"]
    assert "min" not in constraints["capital"], (
        "a recurring card must not advertise the bankroll floor"
    )


def test_direct_edit_matches_the_conversational_edit_artifact() -> None:
    """The §3.4 identity requirement, proven against the real confirm stage.

    Path A drives the typed endpoint. Path B applies the same edit through the
    conversational machinery: the planner's resolved operations applied by the
    shared applier, then the real confirm stage rebuilding the launch payload.
    Both must land on the same canonical launch payload hash.
    """
    from argus.agent_runtime.artifact_edit_planner import (
        EditOperation,
        apply_edit_operations,
    )
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.confirmation_artifacts import canonical_payload_hash
    from argus.agent_runtime.stages.confirm import confirm_stage
    from argus.agent_runtime.stages.interpret_internal.confirmation_artifact_edits import (
        apply_resolved_artifact_edit_to_strategy_summary,
    )
    from argus.agent_runtime.state.models import RunState, StrategySummary

    client = _client()
    conversation = _conversation(client)
    source_payload = _confirmation_payload()
    _plant_confirmation(client, conversation["id"], source_payload)

    response = _direct_edit(
        client,
        conversation["id"],
        CONFIRMATION_ID,
        {"capital": 42000, "date_window": {"start": "2023-02-01", "end": "2023-05-31"}},
    )
    assert response.status_code == 200, response.text
    direct_payload = response.json()["message"]["metadata"]["confirmation_payload"]

    from argus.agent_runtime.llm_interpreter_types import LLMDateRangeIntent

    resolved = apply_edit_operations(
        [
            EditOperation(op="set", target="capital", number=42000),
            EditOperation(
                op="set",
                target="date_window",
                date_window=LLMDateRangeIntent(
                    kind="explicit_range",
                    start="2023-02-01",
                    end="2023-05-31",
                    confidence=1.0,
                ),
            ),
        ],
        current_asset_universe=["NFLX"],
    )
    assert not resolved.unsupported
    summary = StrategySummary.model_validate(source_payload["strategy"])
    field_provenance: dict[str, str] = {}
    apply_resolved_artifact_edit_to_strategy_summary(
        resolved,
        candidate=summary,
        field_provenance=field_provenance,
    )
    summary.extra_parameters["field_provenance"] = field_provenance
    state = RunState.new(
        current_user_message="change capital to 42000 and the dates",
        recent_thread_history=[],
    )
    state = state.model_copy(update={"candidate_strategy_draft": summary})
    result = confirm_stage(
        state=state,
        contract=build_default_capability_contract(),
        language="en",
    )
    assert result.outcome == "await_approval"
    conversational_payload = result.stage_patch["confirmation_payload"]

    direct_launch = dict(direct_payload["launch_payload"])
    conversational_launch = dict(conversational_payload["launch_payload"])
    assert canonical_payload_hash(direct_launch) == canonical_payload_hash(
        conversational_launch
    ), (
        "a direct edit and the equivalent conversational edit must produce "
        f"one canonical artifact; direct={direct_launch} "
        f"conversational={conversational_launch}"
    )
    for field in ("capital_amount", "date_range", "asset_universe", "strategy_type"):
        assert (
            direct_payload["strategy"][field]
            == (conversational_payload["strategy"][field])
        )


def test_stale_confirmation_id_conflicts() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])

    response = _direct_edit(
        client,
        conversation["id"],
        "33333333-3333-4333-8333-333333333333",
        {"capital": 25000},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "artifact_action_invalid_state"


def test_repeated_direct_edits_keep_editing_the_same_card() -> None:
    """The card's identity survives any number of in-place edits."""
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])

    first = _direct_edit(client, conversation["id"], CONFIRMATION_ID, {"capital": 20000})
    assert first.status_code == 200
    second = _direct_edit(client, conversation["id"], CONFIRMATION_ID, {"capital": 30000})
    assert second.status_code == 200
    message = second.json()["message"]
    assert message["metadata"]["confirmation_card"]["confirmation_id"] == CONFIRMATION_ID
    assert (
        message["metadata"]["confirmation_payload"]["strategy"]["capital_amount"] == 30000
    )
    assert len(_conversation_messages(client, conversation["id"])) == 1


def test_empty_and_malformed_bodies_are_validation_errors() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])

    assert _direct_edit(client, conversation["id"], CONFIRMATION_ID, {}).status_code == (
        422
    )
    assert (
        _direct_edit(
            client,
            conversation["id"],
            CONFIRMATION_ID,
            {"capital": -5},
        ).status_code
        == 422
    )
    assert (
        _direct_edit(
            client,
            conversation["id"],
            CONFIRMATION_ID,
            {"date_window": {"start": "2023-06-30", "end": "2023-01-02"}},
        ).status_code
        == 422
    )


def test_position_size_confirmation_rejects_capital_edit() -> None:
    client = _client()
    conversation = _conversation(client)
    payload = _confirmation_payload()
    payload["strategy"]["sizing_mode"] = "position_size"
    payload["strategy"]["capital_amount"] = None
    payload["strategy"]["position_size"] = 10
    payload["launch_payload"]["sizing_mode"] = "position_size"
    payload["launch_payload"]["capital_amount"] = None
    payload["launch_payload"]["position_size"] = 10
    _plant_confirmation(client, conversation["id"], payload)

    response = _direct_edit(client, conversation["id"], CONFIRMATION_ID, {"capital": 100})
    assert response.status_code == 409
    card = runtime_confirmation_card(
        {"stage_outcome": "await_approval", "confirmation_payload": payload},
        confirmation_id=CONFIRMATION_ID,
        conversation_id=conversation["id"],
        language="en",
    )
    assert card is not None
    assert card["capabilities"]["direct_edits"] == ["dates", "costs"]


def test_direct_edit_capability_is_emitted_on_ordinary_cards() -> None:
    payload = _confirmation_payload()
    card = runtime_confirmation_card(
        {"stage_outcome": "await_approval", "confirmation_payload": payload},
        confirmation_id=CONFIRMATION_ID,
        conversation_id="c1",
        language="en",
    )
    assert card is not None
    # Three edit affordances, one behaviour: costs join capital and dates on
    # the in-place path whenever the engine can model them.
    assert card["capabilities"]["direct_edits"] == ["capital", "dates", "costs"]


def test_cost_edit_updates_in_place_through_the_shared_gate() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])

    response = _direct_edit(
        client,
        conversation["id"],
        CONFIRMATION_ID,
        {"fee_rate": 0.002, "slippage": 0.001},
    )
    assert response.status_code == 200, response.text
    message = response.json()["message"]
    payload = message["metadata"]["confirmation_payload"]
    assert payload["confirmation_id"] == CONFIRMATION_ID
    extra = payload["strategy"]["extra_parameters"]
    assert extra["fee_rate"] == 0.002
    assert extra["slippage"] == 0.001
    assert extra["field_provenance"]["fee_rate"] == "explicit_user"
    assert extra["field_provenance"]["slippage"] == "explicit_user"
    fees = payload["optional_parameters"]["fees"]
    slippage = payload["optional_parameters"]["slippage"]
    assert fees["value"] == 0.002 and fees["source"] == "user"
    assert slippage["value"] == 0.001 and slippage["source"] == "user"
    assert len(_conversation_messages(client, conversation["id"])) == 1


def test_over_cap_slippage_is_a_typed_field_error() -> None:
    """The shared resolver is the one cost gate; the drawer shows the refusal
    at the field and the card is untouched."""
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])

    response = _direct_edit(
        client,
        conversation["id"],
        CONFIRMATION_ID,
        {"slippage": 0.9},
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "unsupported_cost_value"
    stored = _conversation_messages(client, conversation["id"])
    payload = stored[-1]["metadata"]["confirmation_payload"]
    assert "slippage" not in (payload["strategy"].get("extra_parameters") or {})


def test_cost_direct_edit_matches_the_conversational_edit_artifact() -> None:
    """The §3.4 identity requirement extended to costs."""
    from argus.agent_runtime.artifact_edit_planner import (
        EditOperation,
        apply_edit_operations,
    )
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.confirmation_artifacts import canonical_payload_hash
    from argus.agent_runtime.stages.confirm import confirm_stage
    from argus.agent_runtime.stages.interpret_internal.confirmation_artifact_edits import (
        apply_resolved_artifact_edit_to_strategy_summary,
    )
    from argus.agent_runtime.state.models import RunState, StrategySummary

    client = _client()
    conversation = _conversation(client)
    source_payload = _confirmation_payload()
    _plant_confirmation(client, conversation["id"], source_payload)

    response = _direct_edit(
        client,
        conversation["id"],
        CONFIRMATION_ID,
        {"fee_rate": 0.002, "slippage": 0.001},
    )
    assert response.status_code == 200, response.text
    direct_payload = response.json()["message"]["metadata"]["confirmation_payload"]

    resolved = apply_edit_operations(
        [
            EditOperation(op="set", target="fees", number=0.002),
            EditOperation(op="set", target="slippage", number=0.001),
        ],
        current_asset_universe=["NFLX"],
    )
    assert not resolved.unsupported
    summary = StrategySummary.model_validate(source_payload["strategy"])
    field_provenance: dict[str, str] = {}
    apply_resolved_artifact_edit_to_strategy_summary(
        resolved,
        candidate=summary,
        field_provenance=field_provenance,
    )
    summary.extra_parameters["field_provenance"] = field_provenance
    state = RunState.new(
        current_user_message="use a 0.2% fee and 0.1% slippage",
        recent_thread_history=[],
    )
    state = state.model_copy(update={"candidate_strategy_draft": summary})
    result = confirm_stage(
        state=state,
        contract=build_default_capability_contract(),
        language="en",
    )
    assert result.outcome == "await_approval"
    conversational_payload = result.stage_patch["confirmation_payload"]
    assert canonical_payload_hash(
        dict(direct_payload["launch_payload"])
    ) == canonical_payload_hash(dict(conversational_payload["launch_payload"]))


def test_out_of_envelope_values_refuse_with_their_exact_codes() -> None:
    """The engine's accepted-value envelope, enforced before a card can mint.

    Every bound is the engine's own (imported constants, never restated); a
    ready card may never promise a run the run-time validator refuses, and
    every refusal names its code so the editor can say why.
    """
    from argus.domain.backtesting.config import (
        MAX_FEE_RATE,
        MAX_STARTING_CAPITAL,
        MIN_STARTING_CAPITAL,
    )

    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])

    refusals = [
        ({"capital": MIN_STARTING_CAPITAL - 1}, "invalid_starting_capital"),
        ({"capital": MAX_STARTING_CAPITAL + 1}, "invalid_starting_capital"),
        (
            {"date_window": {"start": "2029-01-01", "end": "2030-01-01"}},
            "future_end_date",
        ),
        (
            {"date_window": {"start": "2023-03-01", "end": "2023-03-01"}},
            "invalid_chronological_date_range",
        ),
        ({"fee_rate": MAX_FEE_RATE + 0.01}, "unsupported_cost_value"),
    ]
    for body, expected_code in refusals:
        response = _direct_edit(client, conversation["id"], CONFIRMATION_ID, body)
        assert response.status_code == 422, (body, response.text)
        assert response.json()["code"] == expected_code, (body, response.text)

    stored = _conversation_messages(client, conversation["id"])
    assert len(stored) == 1
    payload = stored[0]["metadata"]["confirmation_payload"]
    assert payload["strategy"]["capital_amount"] == 10000, (
        "a refused value must leave the card untouched"
    )
    boundary = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": MIN_STARTING_CAPITAL}
    )
    assert boundary.status_code == 200, boundary.text


def test_card_advertises_the_engine_envelope() -> None:
    """The card's edit constraints are the engine's bounds by import, so the
    client renders backend truth without owning it."""
    from datetime import date

    from argus.domain.backtesting.config import (
        MAX_FEE_RATE,
        MAX_SLIPPAGE_RATE,
        MAX_STARTING_CAPITAL,
        MIN_STARTING_CAPITAL,
    )
    from argus.domain.market_data.capabilities import ALPACA_EQUITY_HISTORY_START

    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": _confirmation_payload(),
        },
        confirmation_id=CONFIRMATION_ID,
        conversation_id="c1",
        language="en",
    )
    assert card is not None
    constraints = card["capabilities"]["edit_constraints"]
    assert constraints["capital"] == {
        "min": MIN_STARTING_CAPITAL,
        "max": MAX_STARTING_CAPITAL,
    }
    assert constraints["fees"] == {"min": 0.0, "max": MAX_FEE_RATE}
    assert constraints["slippage"] == {"min": 0.0, "max": MAX_SLIPPAGE_RATE}
    assert constraints["date_window"]["max_end"] == date.today().isoformat()
    assert (
        constraints["date_window"]["min_start"]
        == ALPACA_EQUITY_HISTORY_START.isoformat()
    )
