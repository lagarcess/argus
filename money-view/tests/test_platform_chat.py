"""Local chat exercises real finance owners without a live model provider."""

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.interpreter import FixtureInterpreter
from server.platform import chat, commands, runtime
from server.platform.chat_contracts import PlannedTurn, TurnRequest
from server.platform.common import Context, PlatformError
from server.platform.identity import DEMO_PASSWORD


class FakePlanner:
    def __init__(self, plan):
        self.result = PlannedTurn.model_validate({"plan": plan})
        self.packets = []

    async def plan(self, packet, *, store, context):
        self.packets.append(packet)
        return self.result


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "chat.sqlite", FixtureInterpreter())
    with TestClient(app) as client:
        login(client)
        yield client


def login(client, user="user-demo"):
    response = client.post(
        "/api/platform/session/login", json={"user_id": user, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text


def turn(client, **values):
    body = {"turn_id": uuid4().hex, **values}
    response = client.post("/api/platform/chat/turn", json=body)
    assert response.status_code == 200, response.text
    frames = [
        line[6:] for line in response.text.splitlines() if line.startswith("data: ")
    ]
    assert frames[-1] == "[DONE]"
    events = [json.loads(frame) for frame in frames[:-1]]
    assert events[-1]["type"] == "final"
    assert all(
        event["type"] in ("stage_start", "stage_outcome", "final") for event in events
    )
    return events[-1], body, events


def proposal_action():
    return {
        "kind": "proposal",
        "command_name": "goal.create",
        "arguments": {
            "name": "Family trip",
            "currency": "DOP",
            "target_amount": "10000",
            "monthly_contribution": "500",
            "target_date": "2027-09-21",
        },
    }


def test_keyless_text_preserved_and_prepared_reads_are_grounded(client, monkeypatch):
    for key in ("CLARA_LLM_API_KEY", "CLARA_LLM_MODEL", "CLARA_LLM_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    unavailable, body, _ = turn(client, text="Cómo cambian mis gastos?", locale="es-419")
    assert unavailable["status"] == "model_unavailable"
    conversation_id = unavailable["conversation_id"]
    detail = client.get(f"/api/platform/chat/conversations/{conversation_id}").json()
    assert detail["messages"][0]["text"] == body["text"]
    plan = {
        "kind": "read",
        "action": "spending",
        "parameters": {"currency": "DOP", "month": date.today().strftime("%Y-%m")},
    }
    answered, _, events = turn(client, conversation_id=conversation_id, action=plan)
    assert answered["status"] == "completed"
    assert answered["message"]["text"] is None
    card = answered["message"]["cards"][0]
    canonical = client.get(
        f"/api/platform/spending?currency=DOP&month={plan['parameters']['month']}"
    ).json()
    if card["facts"]:
        assert {fact["key"]: fact["value"] for fact in card["facts"]}[
            "spending"
        ] == canonical["spending"]
    replay, _, replay_events = turn(client, **body)
    assert replay == unavailable
    assert len(replay_events) == 1
    assert len(events) == 5


def test_turn_id_conflict_and_conversation_controls(client):
    result, body, _ = turn(
        client,
        action={
            "kind": "calculation",
            "tool_name": "effective_rate",
            "arguments": {"currency": "USD", "nominal_rate_pct": 8},
        },
    )
    assert result["message"]["cards"][0]["card"]["outcome"]["status"] == "succeeded"
    conflict = client.post(
        "/api/platform/chat/turn",
        json={
            **body,
            "action": {
                **body["action"],
                "arguments": {"currency": "USD", "nominal_rate_pct": 9},
            },
        },
    )
    assert conflict.status_code == 409
    key = result["conversation_id"]
    for state in ("archived", "trashed", "active"):
        response = client.patch(
            f"/api/platform/chat/conversations/{key}",
            json={"title": "My comparison", "pinned": True, "state": state},
        )
        assert response.status_code == 200
        assert (
            client.get(f"/api/platform/chat/conversations?state={state}").json()["items"][
                0
            ]["id"]
            == key
        )
    login(client, "user-other")
    assert client.get(f"/api/platform/chat/conversations/{key}").status_code == 404


def test_calculation_followup_preserves_other_arguments_and_original_receipt(client):
    first, _, _ = turn(
        client,
        action={
            "kind": "calculation",
            "tool_name": "effective_rate",
            "arguments": {
                "currency": "KWD",
                "nominal_rate_pct": 8,
                "compounding_per_year": 4,
            },
        },
    )
    original = first["message"]["cards"][0]["card"]
    second, _, _ = turn(
        client,
        conversation_id=first["conversation_id"],
        action={
            "kind": "calculation",
            "tool_name": "effective_rate",
            "artifact_id": original["artifact_id"],
            "arguments": {"nominal_rate_pct": 10},
        },
    )
    changed = second["message"]["cards"][0]["card"]
    assert (
        changed["arguments"]["compounding_per_year"]
        == original["arguments"]["compounding_per_year"]
    )
    assert changed["arguments"]["currency"] == "KWD"
    assert changed["artifact_id"] != original["artifact_id"]
    history = client.get(
        f"/api/platform/chat/conversations/{first['conversation_id']}"
    ).json()
    assert history["messages"][1]["cards"][0]["card"] == original


def test_account_currency_is_verified_and_mismatch_fails(client):
    account = client.get("/api/platform/accounts?currency=DOP").json()["items"][0]
    first, _, _ = turn(
        client,
        account_id=account["id"],
        action={
            "kind": "calculation",
            "tool_name": "effective_rate",
            "arguments": {"nominal_rate_pct": 8},
        },
    )
    card = first["message"]["cards"][0]
    assert card["card"]["arguments"]["currency"] == "DOP"
    assert card["card"]["arguments"]["sources"]["currency"]["kind"] == "account"
    assert card["evidence"][0]["as_of"]
    mismatch, _, _ = turn(
        client,
        account_id=account["id"],
        action={
            "kind": "calculation",
            "tool_name": "effective_rate",
            "arguments": {"currency": "USD", "nominal_rate_pct": 8},
        },
    )
    assert mismatch["code"] == "account_currency_mismatch"


def test_semantic_planner_receives_owned_bounded_context_and_executes_no_write(client):
    planner = FakePlanner(proposal_action())
    client.app.state.chat_planner = planner
    before = client.get("/api/platform/goals").json()["items"]
    result, _, _ = turn(
        client, text="Planifica mi viaje", locale="es-419", currency="DOP"
    )
    assert result["code"] == "confirmation_required"
    assert client.get("/api/platform/goals").json()["items"] == before
    assert len(planner.packets) == 1
    packet = planner.packets[0]
    assert len(packet["accounts"]) <= 30
    assert len(packet["catalog"]["calculations"]) == 11
    assert len(packet["catalog"]["commands"]) >= 20
    assert all(account["id"] != "household-other" for account in packet["accounts"])


def test_proposal_confirm_replay_and_transcript_are_one_receipt(client):
    prepared, _, _ = turn(client, action=proposal_action(), currency="DOP")
    proposal = prepared["message"]["cards"][0]["proposal"]
    path = f"/api/platform/chat/proposals/{proposal['proposal_id']}/confirm"
    body = {"expected_revision": proposal["revision"]}
    first = client.post(path, json=body)
    assert first.status_code == 200, first.text
    replay = client.post(path, json=body)
    assert replay.json() == first.json()
    newer, _, _ = turn(
        client,
        conversation_id=prepared["conversation_id"],
        action=proposal_action(),
        currency="DOP",
    )
    assert (
        newer["message"]["cards"][0]["proposal"]["proposal_id"] != proposal["proposal_id"]
    )
    assert client.post(path, json=body).json() == first.json()
    receipt = first.json()["receipt"]
    assert any(
        item["id"] == receipt["record_id"]
        for item in client.get("/api/platform/goals").json()["items"]
    )
    detail = client.get(
        f"/api/platform/chat/conversations/{prepared['conversation_id']}"
    ).json()
    assert (
        len(
            [
                card
                for message in detail["messages"]
                for card in message["cards"]
                if card["kind"] == "receipt"
            ]
        )
        == 1
    )
    assert detail["messages"][1]["cards"][0]["proposal"]["status"] == "consumed"


def test_keyless_goal_example_reaches_canonical_confirmation(client):
    class Never:
        async def plan(self, *args, **kwargs):
            pytest.fail("a typed example must not call a model")

    client.app.state.chat_planner = Never()
    sample = next(
        example
        for example in client.get("/api/platform/chat/capabilities").json()["examples"]
        if example["id"] == "sample-goal"
    )
    assert all("DOP" in label for label in sample["label"].values())
    before = client.get("/api/platform/goals").json()["items"]
    result, _, _ = turn(client, action=sample["action"], currency="DOP")
    assert result["code"] == "confirmation_required"
    assert client.get("/api/platform/goals").json()["items"] == before
    proposal = result["message"]["cards"][0]["proposal"]
    confirmed = client.post(
        f"/api/platform/chat/proposals/{proposal['proposal_id']}/confirm",
        json={"expected_revision": proposal["revision"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    created = next(
        item
        for item in client.get("/api/platform/goals").json()["items"]
        if item["id"] == confirmed.json()["receipt"]["record_id"]
    )
    for key, value in sample["action"]["arguments"].items():
        assert str(created[key]) == value


@pytest.mark.parametrize("semantic", [False, True])
def test_requested_currency_applies_before_legacy_read_defaults(client, semantic):
    plan = {"kind": "read", "action": "net_worth", "parameters": {}}
    if semantic:
        client.app.state.chat_planner = FakePlanner(plan)
    result, _, _ = turn(
        client,
        currency="DOP",
        **({"text": "Read the selected currency"} if semantic else {"action": plan}),
    )
    assert result["status"] == "completed"
    facts = result["message"]["cards"][0]["facts"]
    assert facts and {fact["currency"] for fact in facts} == {"DOP"}
    missing, _, _ = turn(
        client,
        **({"text": "Read without currency"} if semantic else {"action": plan}),
    )
    assert missing["code"] == "currency_required"


@pytest.mark.parametrize("planned,expected", [("USD", "USD"), (None, "DOP")])
def test_semantic_currency_precedes_ui_default_and_hint_provenance_is_explicit(
    client, planned, expected
):
    arguments = {"nominal_rate_pct": 8, "compounding_per_year": 12}
    if planned:
        arguments["currency"] = planned
    planner = FakePlanner(
        {"kind": "calculation", "tool_name": "effective_rate", "arguments": arguments}
    )
    client.app.state.chat_planner = planner
    final, _, _ = turn(client, text="Calculate this rate", default_currency="DOP")
    assert final["status"] == "completed", final
    assert final["message"]["cards"][0]["card"]["arguments"]["currency"] == expected
    assert final["message"]["cards"][0]["card"]["arguments"]["sources"]["currency"]["kind"] == (
        "user" if planned else "assumption"
    )
    saved = client.get(
        f"/api/platform/chat/conversations/{final['conversation_id']}"
    ).json()
    assert saved["messages"][-1]["cards"][0]["card"]["arguments"]["sources"]["currency"]["kind"] == (
        "user" if planned else "assumption"
    )
    if planned is None:
        revised, _, _ = turn(
            client,
            conversation_id=final["conversation_id"],
            default_currency="DOP",
            action={
                "kind": "calculation",
                "tool_name": "effective_rate",
                "artifact_id": final["message"]["cards"][0]["card"]["artifact_id"],
                "arguments": {"nominal_rate_pct": 9},
            },
        )
        assert revised["message"]["cards"][0]["card"]["arguments"]["sources"]["currency"]["kind"] == "assumption"
    assert planner.packets[0]["explicit_currency"] is None
    assert planner.packets[0]["default_currency_hint"] == {
        "code": "DOP",
        "source": "ui_default",
    }


@pytest.mark.parametrize("resource", ["accounts", "transactions"])
def test_owned_record_currency_overrides_ui_default(client, resource):
    record = client.get(f"/api/platform/{resource}?currency=USD").json()["items"][0]
    final, _, _ = turn(
        client,
        default_currency="DOP",
        action={"kind": "records", "resource": resource, "record_id": record["id"]},
    )
    assert final["status"] == "completed", final
    card = final["message"]["cards"][0]
    assert card["query"]["currency"] == "USD"
    assert {
        field["currency"]
        for field in card["rows"][0]["fields"]
        if field["kind"] == "money"
    } == {"USD"}


@pytest.mark.parametrize("example_id", ["spending", "effective-rate", "net-worth"])
@pytest.mark.parametrize("selected", [False, True])
def test_generic_prepared_examples_use_default_or_verified_account_currency(
    client, example_id, selected
):
    sample = next(
        item
        for item in client.get("/api/platform/chat/capabilities").json()["examples"]
        if item["id"] == example_id
    )
    selection = {}
    if selected:
        selection["account_id"] = client.get(
            "/api/platform/accounts?currency=DOP"
        ).json()["items"][0]["id"]
    final, _, _ = turn(
        client, default_currency="USD", action=sample["action"], **selection
    )
    assert final["status"] == "completed", final
    card = final["message"]["cards"][0]
    expected = "DOP" if selected else "USD"
    if card["kind"] == "calculation":
        assert card["card"]["arguments"]["currency"] == expected
    else:
        assert card["facts"] and {fact["currency"] for fact in card["facts"]} == {
            expected
        }


def test_ui_default_never_overrides_current_artifacts_or_explicit_account_conflicts(
    client,
):
    calc = {
        "kind": "calculation",
        "tool_name": "effective_rate",
        "arguments": {
            "currency": "USD",
            "nominal_rate_pct": 8,
            "compounding_per_year": 12,
        },
    }
    original, _, _ = turn(client, default_currency="DOP", action=calc)
    edit = {
        "kind": "calculation",
        "tool_name": "effective_rate",
        "artifact_id": original["message"]["cards"][0]["card"]["artifact_id"],
        "arguments": {"nominal_rate_pct": 9},
    }
    continued, _, _ = turn(
        client,
        conversation_id=original["conversation_id"],
        default_currency="DOP",
        action=edit,
    )
    assert continued["message"]["cards"][0]["card"]["arguments"]["currency"] == "USD"
    account = client.get("/api/platform/accounts?currency=DOP").json()["items"][0]
    conflict, _, _ = turn(
        client, account_id=account["id"], default_currency="USD", action=calc
    )
    assert conflict["code"] == "account_currency_mismatch"
    proposal = proposal_action()
    proposal["arguments"]["currency"] = "USD"
    prepared, _, _ = turn(client, default_currency="DOP", action=proposal)
    current = prepared["message"]["cards"][0]["proposal"]
    revised, _, _ = turn(
        client,
        conversation_id=prepared["conversation_id"],
        default_currency="DOP",
        action={
            "kind": "revise_proposal",
            "proposal_id": current["proposal_id"],
            "revision": current["revision"],
            "changes": {"monthly_contribution": "750"},
        },
    )
    assert {
        source["code"]
        for source in revised["message"]["cards"][0]["proposal"]["currency"]
    } == {"USD"}
    proposal["arguments"].pop("currency")
    defaulted, _, _ = turn(client, default_currency="DOP", action=proposal)
    assert defaulted["code"] == "confirmation_required", defaulted
    assert {
        source["code"]
        for source in defaulted["message"]["cards"][0]["proposal"]["currency"]
    } == {"DOP"}
    assert defaulted["message"]["cards"][0]["proposal"]["currency"][0]["kind"] == "ui_default"
    assert revised["message"]["cards"][0]["proposal"]["currency"][0]["kind"] == "explicit"
    defaulted_proposal = defaulted["message"]["cards"][0]["proposal"]
    defaulted_revision, _, _ = turn(
        client,
        conversation_id=defaulted["conversation_id"],
        default_currency="DOP",
        action={
            "kind": "revise_proposal",
            "proposal_id": defaulted_proposal["proposal_id"],
            "revision": defaulted_proposal["revision"],
            "changes": {"monthly_contribution": "750"},
        },
    )
    assert defaulted_revision["message"]["cards"][0]["proposal"]["currency"][0]["kind"] == "ui_default"
    saved = client.get(
        f"/api/platform/chat/conversations/{defaulted['conversation_id']}"
    ).json()
    assert saved["messages"][-1]["cards"][0]["proposal"]["currency"][0]["kind"] == "ui_default"


def test_unknown_ui_currency_hint_is_rejected_before_any_turn_is_saved(client):
    before = client.get("/api/platform/chat/conversations").json()["total"]
    response = client.post(
        "/api/platform/chat/turn",
        json={"turn_id": uuid4().hex, "text": "Hello", "default_currency": "XYZ"},
    )
    assert response.status_code == 422
    assert client.get("/api/platform/chat/conversations").json()["total"] == before


@pytest.mark.parametrize(
    "plan",
    [
        {"kind": "read", "action": "net_worth", "parameters": {"currency": "DOP"}},
        {"kind": "records", "resource": "accounts", "currency": "DOP"},
        {
            "kind": "calculation",
            "tool_name": "effective_rate",
            "arguments": {
                "currency": "DOP",
                "nominal_rate_pct": 8,
                "compounding_per_year": 12,
            },
        },
        proposal_action(),
    ],
)
@pytest.mark.parametrize("account_bound", [False, True])
def test_currency_conflict_is_rejected_for_every_financial_capability(
    client, plan, account_bound
):
    selection = {}
    if account_bound:
        account = client.get("/api/platform/accounts?currency=DOP").json()["items"][0]
        selection["account_id"] = account["id"]
    result, _, _ = turn(client, action=plan, currency="USD", **selection)
    assert result["status"] == "failed"
    assert result["code"] == (
        "command_currency_mismatch"
        if plan["kind"] == "proposal"
        else "account_currency_mismatch"
        if account_bound
        else "currency_context_mismatch"
    )
    assert result["message"]["cards"] == []


def test_selected_account_checks_explicit_request_when_plan_currency_is_omitted(client):
    account = client.get("/api/platform/accounts?currency=DOP").json()["items"][0]
    result, _, _ = turn(
        client,
        account_id=account["id"],
        currency="USD",
        action={
            "kind": "calculation",
            "tool_name": "effective_rate",
            "arguments": {"nominal_rate_pct": 8, "compounding_per_year": 12},
        },
    )
    assert result["code"] == "account_currency_mismatch"


@pytest.mark.parametrize("resource", ["accounts", "transactions"])
@pytest.mark.parametrize(
    "requested,planned",
    [
        (None, None),
        ("DOP", None),
        (None, "DOP"),
        ("DOP", "DOP"),
        ("USD", None),
        (None, "USD"),
        ("USD", "USD"),
        ("DOP", "USD"),
    ],
)
def test_exact_record_currency_comes_from_owned_reference(
    client, resource, requested, planned
):
    record = client.get(f"/api/platform/{resource}?currency=DOP").json()["items"][0]
    plan = {"kind": "records", "resource": resource, "record_id": record["id"]}
    if planned is not None:
        plan["currency"] = planned
    final, _, _ = turn(client, action=plan, currency=requested)
    if "USD" in (requested, planned):
        assert final["status"] == "failed", final
        assert final["code"] in ("account_currency_mismatch", "currency_context_mismatch")
        assert final["message"]["cards"] == []
    else:
        assert final["status"] == "completed", final
        card = final["message"]["cards"][0]
        assert card["query"]["currency"] == record["currency"]
        assert {
            field["currency"]
            for field in card["rows"][0]["fields"]
            if field["kind"] == "money"
        } == {record["currency"]}


@pytest.mark.parametrize("resource", ["accounts", "transactions"])
def test_exact_record_unknown_and_conflicting_account_context_fail_before_read(
    client, resource
):
    missing, _, _ = turn(
        client,
        currency="USD",
        action={"kind": "records", "resource": resource, "record_id": "missing-record"},
    )
    assert missing["status"] == "failed"
    assert missing["code"].endswith("not_found")
    record = client.get(f"/api/platform/{resource}?currency=DOP").json()["items"][0]
    selected = next(
        account
        for account in client.get("/api/platform/accounts").json()["items"]
        if account["id"]
        != (record["id"] if resource == "accounts" else record["account_id"])
    )
    conflict, _, _ = turn(
        client,
        account_id=selected["id"],
        action={"kind": "records", "resource": resource, "record_id": record["id"]},
    )
    assert conflict["code"] == "account_context_mismatch"


def test_record_currency_resolution_and_fact_capture_share_one_snapshot(
    client, monkeypatch
):
    account = client.get("/api/platform/accounts?currency=DOP").json()["items"][0]
    original = commands.CommandService.resolve_record
    changed = False

    def resolve(service, context, kind, record_id):
        nonlocal changed
        record = original(service, context, kind, record_id)
        if record_id == account["id"] and not changed:
            changed = True

            def concurrent_change():
                with service.store.connection(write=True) as db:
                    db.execute(
                        "UPDATE p_accounts SET currency='USD' WHERE id=?", (record_id,)
                    )
                    db.execute(
                        "UPDATE p_transactions SET currency='USD' WHERE account_id=?",
                        (record_id,),
                    )

            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(concurrent_change).result(timeout=5)
        return record

    monkeypatch.setattr(commands.CommandService, "resolve_record", resolve)
    final, _, _ = turn(
        client,
        action={"kind": "records", "resource": "accounts", "record_id": account["id"]},
        currency="DOP",
    )
    assert final["status"] == "completed", final
    card = final["message"]["cards"][0]
    assert card["query"]["currency"] == card["rows"][0]["fields"][-1]["currency"] == "DOP"
    current = next(
        row
        for row in client.get("/api/platform/accounts").json()["items"]
        if row["id"] == account["id"]
    )
    assert current["currency"] == "USD"


def test_calculation_anchor_preserves_currency_and_new_calculation_accepts_explicit_currency(
    client,
):
    action = {
        "kind": "calculation",
        "tool_name": "effective_rate",
        "arguments": {
            "currency": "DOP",
            "nominal_rate_pct": 8,
            "compounding_per_year": 12,
        },
    }
    original, _, _ = turn(client, action=action)
    card = original["message"]["cards"][0]["card"]
    edit = {
        "kind": "calculation",
        "tool_name": "effective_rate",
        "artifact_id": card["artifact_id"],
        "arguments": {"nominal_rate_pct": 10},
    }
    retained, _, _ = turn(
        client, conversation_id=original["conversation_id"], action=edit
    )
    assert retained["message"]["cards"][0]["card"]["arguments"]["currency"] == "DOP"
    rejected, _, _ = turn(
        client, conversation_id=original["conversation_id"], action=edit, currency="USD"
    )
    assert rejected["code"] == "currency_context_mismatch"
    changed, _, _ = turn(
        client,
        conversation_id=original["conversation_id"],
        action={**edit, "arguments": {**edit["arguments"], "currency": "USD"}},
        currency="USD",
    )
    assert changed["code"] == "invalid_calculation_edit"
    standalone, _, _ = turn(
        client,
        action={**action, "arguments": {**action["arguments"], "currency": "USD"}},
        currency="USD",
    )
    assert standalone["status"] == "completed", standalone
    assert standalone["message"]["cards"][0]["card"]["arguments"]["currency"] == "USD"
    missing, _, _ = turn(
        client,
        conversation_id=original["conversation_id"],
        action={
            **edit,
            "artifact_id": "missing-artifact",
            "arguments": {"currency": "USD"},
        },
        currency="USD",
    )
    assert missing["code"] == "calculation_artifact_not_found"


def test_household_partner_reads_proposals_and_continues_without_confirmation_authority(
    client,
):
    result, _, _ = turn(client, action=proposal_action(), currency="DOP")
    proposal = result["message"]["cards"][0]["proposal"]
    login(client, "user-partner")
    detail = client.get(f"/api/platform/chat/conversations/{result['conversation_id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["messages"][1]["cards"][0]["proposal"] == proposal
    client.app.state.chat_planner = FakePlanner({"kind": "read", "action": "net_worth"})
    continued, _, _ = turn(
        client,
        conversation_id=result["conversation_id"],
        text="Review this",
        currency="DOP",
    )
    assert continued["status"] == "completed", continued
    base = f"/api/platform/chat/proposals/{proposal['proposal_id']}"
    for action in ("confirm", "cancel"):
        assert (
            client.post(
                f"{base}/{action}", json={"expected_revision": proposal["revision"]}
            ).status_code
            == 404
        )
    assert (
        client.patch(
            base,
            json={
                "expected_revision": proposal["revision"],
                "request_id": uuid4().hex,
                "changes": {"name": "Changed"},
            },
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "requested,planned",
    [
        (None, None),
        ("DOP", None),
        (None, "DOP"),
        ("USD", None),
        (None, "USD"),
        ("USD", "USD"),
    ],
)
def test_proposal_record_currency_is_resolved_by_command_owner(
    client, requested, planned
):
    goal = next(
        item
        for item in client.get("/api/platform/goals").json()["items"]
        if item["currency"] == "DOP"
    )
    changes = {"monthly_contribution": "500"}
    if planned:
        changes["currency"] = planned
    final, _, _ = turn(
        client,
        currency=requested,
        action={
            "kind": "proposal",
            "command_name": "goal.edit",
            "arguments": {"record_id": goal["id"], "changes": changes},
        },
    )
    if "USD" in (requested, planned):
        assert final["status"] == "failed", final
        assert final["code"] in ("command_currency_mismatch", "currency_context_mismatch")
    else:
        assert final["code"] == "confirmation_required", final
        assert {
            source["code"]
            for source in final["message"]["cards"][0]["proposal"]["currency"]
        } == {"DOP"}
    unchanged = next(
        item
        for item in client.get("/api/platform/goals").json()["items"]
        if item["id"] == goal["id"]
    )
    assert unchanged == goal


def test_proposal_unknown_record_and_flexible_explicit_new_currency(client):
    missing, _, _ = turn(
        client,
        currency="DOP",
        action={
            "kind": "proposal",
            "command_name": "goal.edit",
            "arguments": {
                "record_id": "missing-goal",
                "changes": {"monthly_contribution": "500"},
            },
        },
    )
    assert missing["status"] == "failed"
    assert missing["code"].endswith("not_found")
    action = proposal_action()
    action["arguments"]["currency"] = "USD"
    final, _, _ = turn(client, currency="USD", action=action)
    assert final["code"] == "confirmation_required", final
    assert {
        source["code"] for source in final["message"]["cards"][0]["proposal"]["currency"]
    } == {"USD"}


@pytest.mark.parametrize("requested", [None, "DOP", "USD"])
def test_current_proposal_currency_is_preserved_and_unknown_anchor_fails(
    client, requested
):
    initial, _, _ = turn(client, action=proposal_action(), currency="DOP")
    proposal = initial["message"]["cards"][0]["proposal"]
    action = {
        "kind": "revise_proposal",
        "proposal_id": proposal["proposal_id"],
        "revision": proposal["revision"],
        "changes": {"monthly_contribution": "750"},
    }
    final, _, _ = turn(
        client,
        conversation_id=initial["conversation_id"],
        currency=requested,
        action=action,
    )
    if requested == "USD":
        assert final["code"] == "currency_context_mismatch"
    else:
        assert final["code"] == "confirmation_required", final
        revised = final["message"]["cards"][0]["proposal"]
        assert {source["code"] for source in revised["currency"]} == {"DOP"}
        assert revised["arguments"]["monthly_contribution"] == "750"
    unknown, _, _ = turn(
        client,
        conversation_id=initial["conversation_id"],
        currency=requested,
        action={**action, "proposal_id": "missing-proposal"},
    )
    assert unknown["code"] == "proposal_not_found"


@pytest.mark.parametrize(
    "plan",
    [
        {"kind": "records", "resource": "accounts"},
        {"kind": "records", "resource": "transactions"},
        {
            "kind": "calculation",
            "tool_name": "effective_rate",
            "arguments": {"nominal_rate_pct": 8, "compounding_per_year": 12},
        },
        proposal_action(),
    ],
)
def test_unknown_selected_account_never_becomes_a_currency_hint(client, plan):
    final, _, _ = turn(client, account_id="missing-account", currency="DOP", action=plan)
    assert final["status"] == "failed"
    assert final["code"] == "account_not_found"


def test_conversation_export_is_complete_private_and_bounded(client, monkeypatch):
    result, _, _ = turn(client, action=proposal_action(), currency="DOP")
    conversation_id = result["conversation_id"]
    proposal = result["message"]["cards"][0]["proposal"]
    confirmed = client.post(
        f"/api/platform/chat/proposals/{proposal['proposal_id']}/confirm",
        json={"expected_revision": proposal["revision"]},
    ).json()
    context = Context("user-demo", "household-demo", "owner", "test")
    with client.app.state.store.connection(write=True) as db:
        for _ in range(51):
            chat._insert_message(
                db,
                context,
                conversation_id,
                chat._message(uuid4().hex, text="Saved note"),
            )
        expected = [
            json.loads(row[0])
            for row in db.execute(
                "SELECT document FROM p_chat_messages WHERE conversation_id=? ORDER BY created_at,rowid",
                (conversation_id,),
            )
        ]
    path = f"/api/platform/chat/conversations/{conversation_id}/export"
    exported = client.get(path)
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    assert exported.headers["cache-control"] == "no-store"
    payload = exported.json()
    assert payload["local_only"] is True
    assert payload["scope"] == "private_household"
    assert payload["total"] == len(expected) > 50
    assert payload["messages"] == expected
    assert confirmed["message"] in payload["messages"]
    assert "request_document" not in exported.text
    assert "plan_document" not in exported.text
    client.patch(
        f"/api/platform/chat/conversations/{conversation_id}", json={"state": "archived"}
    )
    assert client.get(path).json()["messages"] == expected
    monkeypatch.setattr(chat, "MAX_EXPORT_ROWS", len(expected) - 1)
    assert client.get(path).status_code == 413
    monkeypatch.setattr(chat, "MAX_EXPORT_ROWS", 10_000)
    monkeypatch.setattr(chat, "MAX_EXPORT_BYTES", 10)
    assert client.get(path).status_code == 413
    login(client, "user-other")
    assert client.get(path).status_code == 404


def test_export_rejects_context_captured_before_household_reset(client):
    result, _, _ = turn(client, action=proposal_action(), currency="DOP")
    captured = Context("user-demo", "household-demo", "owner", "test")
    reset = client.post(
        "/api/platform/settings/data/reset",
        json={"confirmation": "RESET THIS HOUSEHOLD"},
    )
    assert reset.status_code == 200
    with pytest.raises(PlatformError, match="household_data_changed"):
        chat.export_conversation(
            result["conversation_id"], client.app.state.store, captured
        )


def test_receipt_append_failure_rolls_back_domain_write(client, monkeypatch):
    prepared, _, _ = turn(client, action=proposal_action(), currency="DOP")
    proposal = prepared["message"]["cards"][0]["proposal"]
    original = chat._insert_message

    def fail_receipt(db, context, conversation, message):
        if message["code"] == "command_completed":
            raise PlatformError("test_append_failure", 409)
        original(db, context, conversation, message)

    monkeypatch.setattr(chat, "_insert_message", fail_receipt)
    before = client.get("/api/platform/goals").json()
    failed = client.post(
        f"/api/platform/chat/proposals/{proposal['proposal_id']}/confirm",
        json={"expected_revision": proposal["revision"]},
    )
    assert failed.status_code == 409
    assert client.get("/api/platform/goals").json() == before
    assert (
        commands.CommandService(client.app.state.store)
        .get(
            Context("user-demo", "household-demo", "owner", "test"),
            proposal["proposal_id"],
        )
        .status
        == "pending"
    )


def test_revision_preserves_unmentioned_fields_and_cancel_hydrates(client):
    prepared, _, _ = turn(client, action=proposal_action(), currency="DOP")
    proposal = prepared["message"]["cards"][0]["proposal"]
    patched = client.patch(
        f"/api/platform/chat/proposals/{proposal['proposal_id']}",
        json={
            "expected_revision": proposal["revision"],
            "request_id": uuid4().hex,
            "changes": {"target_amount": "12000"},
        },
    )
    assert patched.status_code == 200, patched.text
    revised = patched.json()["proposal"]
    assert (
        revised["arguments"]["monthly_contribution"]
        == proposal["arguments"]["monthly_contribution"]
    )
    canceled = client.post(
        f"/api/platform/chat/proposals/{revised['proposal_id']}/cancel",
        json={"expected_revision": revised["revision"]},
    )
    assert canceled.status_code == 200, canceled.text
    messages = client.get(
        f"/api/platform/chat/conversations/{prepared['conversation_id']}"
    ).json()["messages"]
    assert messages[-1]["cards"][0]["proposal"]["status"] == "cancelled"


@pytest.mark.parametrize(
    "operation,user", [("reset", "user-demo"), ("delete", "user-other")]
)
def test_paused_semantic_turn_cannot_resurrect_after_reset_or_delete(
    client, operation, user
):
    login(client, user)
    entered, release = threading.Event(), threading.Event()

    class Paused(FakePlanner):
        async def plan(self, packet, *, store, context):
            async with runtime.model_admission(store, context):
                entered.set()
                assert await asyncio.to_thread(release.wait, 5)
                return self.result

    client.app.state.chat_planner = Paused(
        {"kind": "clarify", "question": "Which account?"}
    )
    second = TestClient(client.app)
    login(second, user)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(turn, client, text="Private context before deletion")
        try:
            assert entered.wait(5)
            if operation == "reset":
                response = second.post(
                    "/api/platform/settings/data/reset",
                    json={"confirmation": "RESET THIS HOUSEHOLD"},
                )
            else:
                response = second.request(
                    "DELETE",
                    "/api/platform/settings/account",
                    json={
                        "confirmation": "DELETE MY LOCAL ACCOUNT",
                        "current_password": DEMO_PASSWORD,
                    },
                )
            assert response.status_code == 200, response.text
        finally:
            release.set()
        final, _, _ = pending.result(timeout=10)
    second.close()
    assert final["status"] == "failed"
    assert final["message"] is None
    with client.app.state.store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM p_chat_messages").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM p_chat_turns").fetchone()[0] == 0
        assert (
            db.execute("SELECT COUNT(*) FROM p_runtime_model_leases").fetchone()[0] == 0
        )
    if operation == "reset":
        fresh, _, _ = turn(
            client,
            action={
                "kind": "read",
                "action": "spending",
                "parameters": {"currency": "DOP"},
            },
        )
        assert fresh["status"] == "completed"


@pytest.mark.asyncio
async def test_cancelled_execution_reuses_durable_plan_without_second_model(client):
    store, identity = client.app.state.store, client.app.state.identity
    context = Context("user-demo", "household-demo", "owner", "test")
    request = TurnRequest(turn_id=uuid4().hex, text="What is the effective rate?")
    reservation = chat.begin_turn(store, context, request)
    planned = {
        "kind": "calculation",
        "tool_name": "effective_rate",
        "arguments": {"currency": "USD", "nominal_rate_pct": 8},
    }
    chat.checkpoint_plan(store, context, request.turn_id, reservation["token"], planned)
    chat.mark_interrupted(store, context, request.turn_id, reservation["token"])
    retry = chat.begin_turn(store, context, request)

    class Never:
        async def plan(self, *args, **kwargs):
            pytest.fail("a retained plan must not call the model twice")

    final = await chat.run_turn(
        store, identity, context, request, retry, Never(), lambda event: None
    )
    assert final["status"] == "completed"
    assert chat.transcript(store, context, final["conversation_id"])["total"] == 2


def test_record_read_filters_share_canonical_rows_and_evidence(client):
    account = client.get("/api/platform/accounts?currency=DOP").json()["items"][0]
    plan = {
        "kind": "records",
        "resource": "transactions",
        "account_id": account["id"],
        "limit": 3,
        "offset": 2,
    }
    result, _, _ = turn(client, action=plan)
    assert result["status"] == "completed", result
    card = result["message"]["cards"][0]
    assert card["query"]["account_id"] == account["id"]
    assert card["query"]["currency"] == account["currency"]
    assert card["query"]["offset"] == plan["offset"]
    canonical = client.get(
        f"/api/platform/transactions?account_id={account['id']}&currency=DOP&limit=3&offset=2"
    ).json()
    assert card["total"] == canonical["total"]
    assert [row["record_id"] for row in card["rows"]] == [
        row["id"] for row in canonical["items"]
    ]
    for row, saved in zip(card["rows"], canonical["items"], strict=True):
        assert (
            next(field for field in row["fields"] if field["key"] == "amount")["value"]
            == saved["amount"]
        )
        assert row["evidence"] == [saved["source"]]
        assert row["target"]["record_id"] == saved["id"]
    account_result, _, _ = turn(
        client,
        action={"kind": "records", "resource": "accounts", "record_id": account["id"]},
    )
    account_card = account_result["message"]["cards"][0]
    assert account_card["total"] == 1
    assert account_card["rows"][0]["fields"][-1]["value"] == account["balance"]


def test_history_and_context_are_bounded_and_failed_turn_finishes(client):
    class BrokenPlanner:
        async def plan(self, *args, **kwargs):
            raise RuntimeError("synthetic internal failure with private text")

    client.app.state.chat_planner = BrokenPlanner()
    failed, _, _ = turn(client, text="Do not leak this request into logs")
    assert failed["status"] == "failed"
    assert failed["code"] == "chat_unavailable"
    assert failed["message"]["text"] is None
    for _ in range(4):
        turn(
            client,
            conversation_id=failed["conversation_id"],
            action={"kind": "records", "resource": "accounts", "limit": 1},
        )
    newest = client.get(
        f"/api/platform/chat/conversations/{failed['conversation_id']}?limit=3&offset=0"
    ).json()
    older = client.get(
        f"/api/platform/chat/conversations/{failed['conversation_id']}?limit=3&offset=3"
    ).json()
    assert newest["total"] == older["total"] == 10
    assert len(newest["messages"]) == len(older["messages"]) == 3
    assert not {row["id"] for row in newest["messages"]} & {
        row["id"] for row in older["messages"]
    }
    assert (
        client.get(
            f"/api/platform/chat/conversations/{failed['conversation_id']}?limit=101"
        ).status_code
        == 422
    )


def test_concurrent_duplicate_turn_is_observable_without_second_plan(client):
    entered, release = threading.Event(), threading.Event()

    class Paused(FakePlanner):
        async def plan(self, packet, *, store, context):
            self.packets.append(packet)
            entered.set()
            assert await asyncio.to_thread(release.wait, 5)
            return self.result

    planner = Paused({"kind": "clarify", "question": "Which account?"})
    client.app.state.chat_planner = planner
    body = {"turn_id": uuid4().hex, "text": "Help with this account"}
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(turn, client, **body)
        try:
            assert entered.wait(5)
            duplicate, _, _ = turn(client, **body)
            assert duplicate["status"] == "in_progress"
            assert duplicate["message"] is None
        finally:
            release.set()
        finished, _, _ = pending.result(timeout=10)
    assert finished["status"] == "completed"
    assert len(planner.packets) == 1
    assert (
        client.get(
            f"/api/platform/chat/conversations/{finished['conversation_id']}"
        ).json()["total"]
        == 2
    )
