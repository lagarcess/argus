"""A saved tax worksheet retains the exact sources and result the user reviewed."""

import sqlite3
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from platform_identity_factory import identity_context
from server.platform import commands, services, tax_estate
from server.platform.common import PlatformError, get_context, get_store
from server.platform.service_contracts import TaxItem, TaxScenario
from server.store import Store


@pytest.fixture
def fixture(tmp_path):
    store = Store(tmp_path / "tax-artifacts.sqlite")
    context = identity_context(store)
    services.initialize(store)
    commands.initialize(store)
    state = {"context": context}
    app = FastAPI()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_context] = lambda: state["context"]
    app.include_router(services.router)

    @app.exception_handler(PlatformError)
    async def error_handler(request, error):
        return JSONResponse({"error": error.code}, status_code=error.status)

    with TestClient(app) as client:
        yield store, context, state, client


def test_manual_and_command_scenarios_are_owned_immutable_records(fixture):
    store, ctx, state, client = fixture
    payload = {"organizer_id": "tax-demo", "user_rate_pct": "10"}
    manual = client.post("/api/platform/tax/scenario", json=payload).json()
    assert manual["id"].startswith("tax-scenario-")
    assert manual["inputs"]["organizer"]["id"] == "tax-demo"
    assert manual["inputs"]["user_rate_pct"] == "10"
    assert manual["inputs"]["items"] and manual["recorded_at"]
    reopened = Store(store.path)
    assert (
        tax_estate.get_tax_scenario(manual["id"], store=reopened, context=ctx) == manual
    )
    assert client.get(f"/api/platform/tax/scenarios/{manual['id']}").json() == manual

    service = commands.CommandService(store)
    proposal = service.prepare(
        ctx, "tax.scenario", payload, "tax-conversation", "tax-request"
    )
    receipt = service.confirm(ctx, proposal.proposal_id, proposal.revision)
    saved = client.get(f"/api/platform/tax/scenarios/{receipt.record_id}").json()
    assert saved["id"] == receipt.record_id != proposal.proposal_id
    assert receipt.target.query == {"record_id": saved["id"], "tab": "tax"}
    assert receipt.evidence[0].model_dump(mode="json") == saved["evidence"]
    assert saved["scenario_amount"] == manual["scenario_amount"]
    with store.connection(write=True) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable_tax_scenario"):
            db.execute(
                "UPDATE p_tax_scenarios SET document='{}' WHERE id=?", (saved["id"],)
            )

    tax_estate.add_tax_item(
        TaxItem(
            organizer_id="tax-demo",
            kind="expense",
            title="Later expense",
            amount="100",
            effective_on="2026-09-20",
        ),
        store=store,
        context=ctx,
    )
    newer = tax_estate.tax_scenario(TaxScenario(**payload), store=store, context=ctx)
    assert newer["scenario_amount"] != saved["scenario_amount"]
    assert len(newer["inputs"]["items"]) == len(saved["inputs"]["items"]) + 1
    assert client.get(f"/api/platform/tax/scenarios/{saved['id']}").json() == saved
    assert service.confirm(ctx, proposal.proposal_id, proposal.revision) == receipt

    first_page = client.get(
        "/api/platform/tax/scenarios?organizer_id=tax-demo&limit=1"
    ).json()
    second_page = client.get(
        "/api/platform/tax/scenarios?organizer_id=tax-demo&limit=1&offset=1"
    ).json()
    assert first_page["count"] == 3 and len(first_page["items"]) == 1
    assert first_page["items"][0]["id"] != second_page["items"][0]["id"]
    assert "inputs" not in first_page["items"][0]
    assert (
        client.get(
            "/api/platform/tax/scenarios?organizer_id=tax-demo&limit=101"
        ).status_code
        == 422
    )

    state["context"] = identity_context(
        store, user_id="tax-other", household_id="tax-other"
    )
    assert client.get(f"/api/platform/tax/scenarios/{saved['id']}").status_code == 404
    assert (
        client.get("/api/platform/tax/scenarios?organizer_id=tax-demo").status_code == 404
    )
    assert client.post("/api/platform/tax/scenario", json=payload).status_code == 404


def test_scenario_export_reset_and_failed_receipt_are_atomic(fixture):
    store, ctx, _, client = fixture
    service = commands.CommandService(store)
    proposal = service.prepare(
        ctx,
        "tax.scenario",
        {"organizer_id": "tax-demo", "user_rate_pct": "0"},
        "tax",
        "first",
    )

    def fail_append(bound, context, receipt):
        raise RuntimeError("transcript append failed")

    with pytest.raises(RuntimeError, match="transcript append failed"):
        service.confirm(
            ctx, proposal.proposal_id, proposal.revision, on_receipt=fail_append
        )
    with store.connection() as db:
        assert services.export_data(db, ctx)["p_tax_scenarios"] == []
        assert commands.usage_data(db, ctx)["receipts"] == 0
    receipt = service.confirm(ctx, proposal.proposal_id, proposal.revision)
    with store.connection(write=True) as db:
        assert (
            services.export_data(db, ctx)["p_tax_scenarios"][0]["id"] == receipt.record_id
        )
        before = services.usage_data(db, ctx)["service_records"]
        assert before > 0
        commands.clear_data(db, ctx)
        services.clear_data(db, ctx)
    services.initialize(store)
    with store.connection() as db:
        assert services.usage_data(db, ctx)["service_records"] == 0
        assert services.export_data(db, ctx)["p_tax_scenarios"] == []
    assert (
        client.get(f"/api/platform/tax/scenarios/{receipt.record_id}").status_code == 404
    )


def test_missing_canonical_artifact_cannot_emit_a_fictitious_target(fixture, monkeypatch):
    store, ctx, _, _ = fixture
    service = commands.CommandService(store)
    proposal = service.prepare(
        ctx,
        "tax.scenario",
        {"organizer_id": "tax-demo", "user_rate_pct": "0"},
        "tax",
        "missing",
    )
    spec = commands.REGISTRY["tax.scenario"]
    monkeypatch.setitem(
        commands.REGISTRY,
        "tax.scenario",
        replace(spec, handler=lambda *args: {"scenario_amount": "0"}),
    )
    with pytest.raises(PlatformError, match="command_artifact_missing"):
        service.confirm(ctx, proposal.proposal_id, proposal.revision)
    assert service.get(ctx, proposal.proposal_id).status == "pending"
    with store.connection() as db:
        assert commands.usage_data(db, ctx)["receipts"] == 0
