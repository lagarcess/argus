"""Personal worksheets and inventories, without tax or legal execution."""

import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, Query

from .common import (
    CURRENCY_DIGITS,
    PlatformError,
    assert_active_context,
    minor_units,
    now,
    require_editor,
)
from .service_contracts import (
    Beneficiaries,
    Checklist,
    Completion,
    Contact,
    ContextDependency,
    Document,
    EstateAsset,
    Organizer,
    OrganizerStatus,
    StoreDependency,
    TaxItem,
    TaxScenario,
    csv_download,
    evidence,
    json_download,
    new_record,
    record,
    rows,
    save,
)

router = APIRouter()


@router.get("/tax")
def tax(*, store: StoreDependency, context: ContextDependency):
    with store.connection() as db:
        return {
            "organizers": rows(db, "p_tax_organizers", context.household_id),
            "items": rows(db, "p_tax_items", context.household_id),
        }


@router.post("/tax/organizers")
def add_organizer(
    payload: Organizer, *, store: StoreDependency, context: ContextDependency
):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        for current in rows(db, "p_tax_organizers", context.household_id):
            if all(current[key] == value for key, value in payload.model_dump().items()):
                return current
        return save(
            db,
            "p_tax_organizers",
            context.household_id,
            {**new_record(payload, "tax"), "status": "open"},
        )


@router.post("/tax/items")
def add_tax_item(payload: TaxItem, *, store: StoreDependency, context: ContextDependency):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        organizer = record(
            db, "p_tax_organizers", context.household_id, payload.organizer_id
        )
        if organizer["status"] == "complete":
            raise PlatformError("organizer_complete", 409)
        if payload.effective_on.year != organizer["year"]:
            raise PlatformError("tax_item_year_mismatch")
        if payload.amount is not None:
            minor_units(payload.amount, organizer["currency"])
        return save(
            db,
            "p_tax_items",
            context.household_id,
            {**new_record(payload, "tax-item"), "completed": False},
        )


@router.patch("/tax/items/{item_id}")
def complete_tax_item(
    item_id: str,
    payload: Completion,
    *,
    store: StoreDependency,
    context: ContextDependency,
):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        item = record(db, "p_tax_items", context.household_id, item_id)
        organizer = record(
            db, "p_tax_organizers", context.household_id, item["organizer_id"]
        )
        if organizer["status"] == "complete":
            raise PlatformError("organizer_complete", 409)
        return save(
            db,
            "p_tax_items",
            context.household_id,
            {**item, "completed": payload.completed},
        )


@router.patch("/tax/organizers/{organizer_id}")
def complete_organizer(
    organizer_id: str,
    payload: OrganizerStatus,
    *,
    store: StoreDependency,
    context: ContextDependency,
):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        organizer = record(db, "p_tax_organizers", context.household_id, organizer_id)
        items = [
            r
            for r in rows(db, "p_tax_items", context.household_id)
            if r["organizer_id"] == organizer_id
        ]
        if payload.status == "complete" and any(
            not r["completed"] for r in items if r["kind"] in ("document", "checklist")
        ):
            raise PlatformError("tax_checklist_incomplete", 409)
        return save(
            db,
            "p_tax_organizers",
            context.household_id,
            {**organizer, "status": payload.status},
        )


@router.post("/tax/scenario")
def tax_scenario(
    payload: TaxScenario, *, store: StoreDependency, context: ContextDependency
):
    """Save one immutable worksheet from the source records visible now."""
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        organizer = record(
            db, "p_tax_organizers", context.household_id, payload.organizer_id
        )
        items = [
            json.loads(row[0])
            for row in db.execute(
                "SELECT document FROM p_tax_items WHERE household_id=? AND json_extract(document,'$.organizer_id')=? ORDER BY id",
                (context.household_id, payload.organizer_id),
            )
        ]
        scenario = new_record(payload, "tax-scenario")
        result = calculate_tax_scenario(payload, organizer, items, scenario)
        document = {
            **scenario,
            **result,
            "inputs": {
                "organizer": organizer,
                "items": items,
                "user_rate_pct": str(payload.user_rate_pct),
            },
        }
        db.execute(
            "INSERT INTO p_tax_scenarios(id,household_id,document) VALUES(?,?,?)",
            (scenario["id"], context.household_id, json.dumps(document)),
        )
        return document


def calculate_tax_scenario(payload, organizer, items, scenario):
    income = sum(
        (Decimal(r["amount"]) for r in items if r["kind"] == "income"), Decimal(0)
    )
    expenses = sum(
        (Decimal(r["amount"]) for r in items if r["kind"] == "expense"), Decimal(0)
    )
    net = income - expenses
    amount = (net * payload.user_rate_pct / 100).quantize(
        Decimal(1).scaleb(-CURRENCY_DIGITS[organizer["currency"]]), rounding=ROUND_HALF_UP
    )
    financial_items = [item for item in items if item["kind"] in ("income", "expense")]
    calculated_at = now()
    source = evidence(
        scenario["id"],
        min(
            (item["effective_on"] for item in financial_items),
            default=calculated_at.date().isoformat(),
        ),
        "calculated",
        "(recorded income - recorded expenses) * user_rate_pct / 100",
    )
    source["inputs"] = [organizer["id"], *[item["id"] for item in financial_items]]
    result = {
        "income": str(income),
        "expenses": str(expenses),
        "net_amount": str(net),
        "user_rate_pct": str(payload.user_rate_pct),
        "scenario_amount": str(amount),
        "currency": organizer["currency"],
        "formula": "(recorded income - recorded expenses) * user_rate_pct / 100",
        "legal_status": "worksheet_only",
        "evidence": source,
        "source_records": [
            {
                "id": item["id"],
                "effective_on": item["effective_on"],
                "recorded_at": item["recorded_at"],
                "kind": item.get("evidence", {}).get("kind", "user"),
            }
            for item in financial_items
        ],
        "rate_evidence": evidence(f"{scenario['id']}-rate", calculated_at.date()),
    }
    return result


@router.get("/tax/scenarios/{scenario_id}")
def get_tax_scenario(
    scenario_id: str, *, store: StoreDependency, context: ContextDependency
):
    with store.connection() as db:
        return record(db, "p_tax_scenarios", context.household_id, scenario_id)


@router.get("/tax/scenarios")
def list_tax_scenarios(
    *,
    store: StoreDependency,
    context: ContextDependency,
    organizer_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    with store.connection() as db:
        record(db, "p_tax_organizers", context.household_id, organizer_id)
        parameters = (context.household_id, organizer_id)
        condition = "household_id=? AND json_extract(document,'$.organizer_id')=?"
        count = db.execute(
            f"SELECT COUNT(*) FROM p_tax_scenarios WHERE {condition}", parameters
        ).fetchone()[0]
        items = [
            dict(row)
            for row in db.execute(
                f"SELECT id,json_extract(document,'$.recorded_at') AS recorded_at,json_extract(document,'$.user_rate_pct') AS user_rate_pct FROM p_tax_scenarios WHERE {condition} ORDER BY rowid DESC LIMIT ? OFFSET ?",
                (*parameters, limit, offset),
            )
        ]
        return {"items": items, "count": count, "limit": limit, "offset": offset}


@router.get("/tax/organizers/{organizer_id}/export")
def export_tax(
    organizer_id: str,
    format: Literal["json", "csv"] = "json",
    *,
    store: StoreDependency,
    context: ContextDependency,
):
    with store.connection() as db:
        organizer = record(db, "p_tax_organizers", context.household_id, organizer_id)
        items = [
            r
            for r in rows(db, "p_tax_items", context.household_id)
            if r["organizer_id"] == organizer_id
        ]
    if format == "json":
        return json_download(
            "tax-worksheet",
            {"legal_status": "worksheet_only", "organizer": organizer, "items": items},
        )
    return csv_download(
        "tax-worksheet",
        [
            "legal_status",
            "country",
            "year",
            "currency",
            "kind",
            "title",
            "amount",
            "effective_on",
            "completed",
        ],
        [
            [
                "worksheet_only",
                organizer["country"],
                organizer["year"],
                organizer["currency"],
                i["kind"],
                i["title"],
                i["amount"],
                i["effective_on"],
                i["completed"],
            ]
            for i in items
        ],
    )


def estate_inventory(db, household):
    return {
        key: rows(db, table, household)
        for key, table in (
            ("assets", "p_estate_assets"),
            ("contacts", "p_estate_contacts"),
            ("beneficiaries", "p_estate_beneficiaries"),
            ("documents", "p_estate_documents"),
            ("checklist", "p_estate_checklist"),
        )
    } | {"legal_status": "inventory_only_no_legal_validity"}


@router.get("/estate")
def estate(*, store: StoreDependency, context: ContextDependency):
    with store.connection() as db:
        return estate_inventory(db, context.household_id)


@router.post("/estate/assets")
def add_asset(
    payload: EstateAsset, *, store: StoreDependency, context: ContextDependency
):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        return save(
            db,
            "p_estate_assets",
            context.household_id,
            new_record(payload, "estate-asset"),
        )


@router.post("/estate/contacts")
def add_contact(payload: Contact, *, store: StoreDependency, context: ContextDependency):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        return save(
            db,
            "p_estate_contacts",
            context.household_id,
            new_record(payload, "estate-contact"),
        )


@router.put("/estate/assets/{asset_id}/beneficiaries")
def set_beneficiaries(
    asset_id: str,
    payload: Beneficiaries,
    *,
    store: StoreDependency,
    context: ContextDependency,
):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        record(db, "p_estate_assets", context.household_id, asset_id)
        for share in payload.shares:
            record(db, "p_estate_contacts", context.household_id, share.contact_id)
        value = {
            "id": asset_id,
            "asset_id": asset_id,
            **payload.model_dump(mode="json"),
            "allocated_pct": str(sum((s.share_pct for s in payload.shares), Decimal(0))),
            "recorded_at": now().isoformat(),
        }
        return save(db, "p_estate_beneficiaries", context.household_id, value)


@router.post("/estate/documents")
def add_document(
    payload: Document, *, store: StoreDependency, context: ContextDependency
):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        return save(
            db,
            "p_estate_documents",
            context.household_id,
            new_record(payload, "estate-doc"),
        )


@router.post("/estate/checklist")
def add_checklist(
    payload: Checklist, *, store: StoreDependency, context: ContextDependency
):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        return save(
            db,
            "p_estate_checklist",
            context.household_id,
            {**new_record(payload, "estate-check"), "completed": False},
        )


@router.patch("/estate/checklist/{item_id}")
def complete_estate_item(
    item_id: str,
    payload: Completion,
    *,
    store: StoreDependency,
    context: ContextDependency,
):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        item = record(db, "p_estate_checklist", context.household_id, item_id)
        return save(
            db,
            "p_estate_checklist",
            context.household_id,
            {**item, "completed": payload.completed},
        )


@router.get("/estate/export")
def export_estate(
    format: Literal["json", "csv"] = "json",
    *,
    store: StoreDependency,
    context: ContextDependency,
):
    with store.connection() as db:
        inventory = estate_inventory(db, context.household_id)
    if format == "json":
        return json_download("estate-inventory", inventory)
    records = [
        [
            inventory["legal_status"],
            kind,
            item["id"],
            key,
            value if isinstance(value, str) else str(value),
        ]
        for kind, items in inventory.items()
        if isinstance(items, list)
        for item in items
        for key, value in item.items()
        if key != "id"
    ]
    return csv_download(
        "estate-inventory", ["legal_status", "kind", "id", "field", "value"], records
    )
