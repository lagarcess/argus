"""Local conversation kernel over the existing finance and declaration owners."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import date
from functools import lru_cache
from time import time
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from langsmith import tracing_context
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from server.argus_core.calculations import get_calculation_declarations
from server.argus_core.tool_contracts import ToolCall
from server.argus_core.tool_declaration import ToolCatalog

from ..store import Store
from . import assistant, ledger
from .assistant_contracts import Parameters
from .chat_contracts import (
    CancelProposal,
    ChatMessage,
    ConfirmProposal,
    Conversation,
    ConversationCreate,
    ConversationPatch,
    FinalEvent,
    PatchProposal,
    PlannedTurn,
    TurnRequest,
)
from .chat_graph import run_conversation_graph
from .chat_model import LocalStructuredPlanner, ModelUnavailable, configured
from .common import (
    CURRENCY_DIGITS,
    Context,
    PlatformError,
    assert_active_context,
    get_context,
    get_store,
    identifier,
    now,
)

router = APIRouter(prefix="/api/platform/chat")
DB = Annotated[Store, Depends(get_store)]
CTX = Annotated[Context, Depends(get_context)]
PAGE = Annotated[int, Query(ge=1, le=100)]
OFFSET = Annotated[int, Query(ge=0, le=100_000)]
MAX_CONTEXT_BYTES = 256 * 1024
MAX_MESSAGE_BYTES = 256 * 1024
MAX_TRANSCRIPT_BYTES = 2 * 1024 * 1024
MAX_EXPORT_BYTES = 8 * 1024 * 1024
MAX_EXPORT_ROWS = 10_000
TURN_LEASE_SECONDS = 45
RECORD_RESOURCES = {"accounts": "account", "transactions": "transaction"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS p_chat_conversations(
 id TEXT PRIMARY KEY,household_id TEXT NOT NULL,user_id TEXT NOT NULL,title TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'active',pinned INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS p_chat_conversation_window ON p_chat_conversations(household_id,state,pinned,updated_at,id);
CREATE TABLE IF NOT EXISTS p_chat_turns(
 id TEXT PRIMARY KEY,household_id TEXT NOT NULL,conversation_id TEXT NOT NULL REFERENCES p_chat_conversations(id) ON DELETE CASCADE,
 payload_hash TEXT NOT NULL,request_document TEXT NOT NULL,status TEXT NOT NULL,
 run_token TEXT NOT NULL,lease_until REAL NOT NULL,plan_document TEXT,result_document TEXT,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS p_chat_turns_active ON p_chat_turns(conversation_id,status,lease_until);
CREATE TABLE IF NOT EXISTS p_chat_messages(
 id TEXT PRIMARY KEY,household_id TEXT NOT NULL,conversation_id TEXT NOT NULL REFERENCES p_chat_conversations(id) ON DELETE CASCADE,
 turn_id TEXT NOT NULL,role TEXT NOT NULL,document TEXT NOT NULL,created_at TEXT NOT NULL,
 UNIQUE(turn_id,role));
CREATE INDEX IF NOT EXISTS p_chat_message_window ON p_chat_messages(household_id,conversation_id,created_at,id);
CREATE TRIGGER IF NOT EXISTS p_chat_message_immutable BEFORE UPDATE ON p_chat_messages
BEGIN SELECT RAISE(ABORT,'immutable_chat_message'); END;
"""


def initialize(store: Store):
    with store.connection(write=True) as db:
        db.executescript(SCHEMA)


def _dump(value) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _limited(value, maximum, code):
    result = _dump(value)
    if len(result.encode()) > maximum:
        raise PlatformError(code, 413)
    return result


def _conversation(db, context, conversation_id, *, active=False):
    row = db.execute(
        "SELECT * FROM p_chat_conversations WHERE id=? AND household_id=?",
        (conversation_id, context.household_id),
    ).fetchone()
    if row is None:
        raise PlatformError("conversation_not_found", 404)
    if active and row["state"] != "active":
        raise PlatformError("conversation_inactive", 409)
    return Conversation.model_validate(dict(row)).model_dump(mode="json")


def _insert_message(db, context, conversation_id, message):
    document = _limited(message, MAX_MESSAGE_BYTES, "chat_message_too_large")
    db.execute(
        "INSERT INTO p_chat_messages VALUES(?,?,?,?,?,?,?)",
        (
            message["id"],
            context.household_id,
            conversation_id,
            message["turn_id"],
            message["role"],
            document,
            message["created_at"],
        ),
    )
    db.execute(
        "UPDATE p_chat_conversations SET updated_at=? WHERE id=?",
        (message["created_at"], conversation_id),
    )


def _message(turn_id, *, role="assistant", text=None, code="completed", cards=()):
    return ChatMessage(
        id=identifier("message"),
        role=role,
        turn_id=turn_id,
        text=text,
        code=code,
        cards=list(cards),
        created_at=now().isoformat(),
    ).model_dump(mode="json")


def _new_conversation(db, context, title):
    key, stamp = identifier("chat"), now().isoformat()
    db.execute(
        "INSERT INTO p_chat_conversations VALUES(?,?,?,?,?,?,?,?)",
        (key, context.household_id, context.user_id, title, "active", 0, stamp, stamp),
    )
    return _conversation(db, context, key)


@router.post("/conversations", status_code=201)
def create_conversation(payload: ConversationCreate, store: DB, context: CTX):
    with store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        return _new_conversation(db, context, payload.title)


@router.get("/conversations")
def list_conversations(
    store: DB, context: CTX, state: str = "active", limit: PAGE = 20, offset: OFFSET = 0
):
    if state not in ("active", "archived", "trashed"):
        raise PlatformError("invalid_conversation_state")
    with store.connection() as db:
        total = db.execute(
            "SELECT COUNT(*) FROM p_chat_conversations WHERE household_id=? AND state=?",
            (context.household_id, state),
        ).fetchone()[0]
        rows = db.execute(
            "SELECT * FROM p_chat_conversations WHERE household_id=? AND state=? ORDER BY pinned DESC,updated_at DESC,id DESC LIMIT ? OFFSET ?",
            (context.household_id, state, limit, offset),
        ).fetchall()
    return {
        "items": [
            Conversation.model_validate(dict(row)).model_dump(mode="json") for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.patch("/conversations/{conversation_id}")
def update_conversation(
    conversation_id: str, payload: ConversationPatch, store: DB, context: CTX
):
    with store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        previous = _conversation(db, context, conversation_id)
        changes = payload.model_dump(exclude_unset=True)
        db.execute(
            "UPDATE p_chat_conversations SET title=?,pinned=?,state=?,updated_at=? WHERE id=? AND household_id=?",
            (
                changes.get("title", previous["title"]),
                int(changes.get("pinned", previous["pinned"])),
                changes.get("state", previous["state"]),
                now().isoformat(),
                conversation_id,
                context.household_id,
            ),
        )
        return _conversation(db, context, conversation_id)


def transcript(store, context, conversation_id, limit=50, offset=0):
    with store.read_snapshot(), store.connection() as db:
        conversation = _conversation(db, context, conversation_id)
        total = db.execute(
            "SELECT COUNT(*) FROM p_chat_messages WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()[0]
        rows = db.execute(
            "SELECT document FROM p_chat_messages WHERE conversation_id=? ORDER BY created_at DESC,rowid DESC LIMIT ? OFFSET ?",
            (conversation_id, limit, offset),
        )
        messages, size = [], 0
        for row in rows:
            size += len(row[0].encode())
            if size > MAX_TRANSCRIPT_BYTES:
                raise PlatformError("chat_transcript_too_large", 413)
            message = json.loads(row[0])
            for card in message["cards"]:
                if card["kind"] == "proposal":
                    card["proposal"] = (
                        _command_service(store)
                        .read_for_conversation(
                            context, card["proposal"]["proposal_id"], conversation_id
                        )
                        .model_dump(mode="json")
                    )
            messages.append(message)
    return {
        "conversation": conversation,
        "messages": list(reversed(messages)),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/conversations/{conversation_id}")
def get_transcript(
    conversation_id: str, store: DB, context: CTX, limit: PAGE = 50, offset: OFFSET = 0
):
    return transcript(store, context, conversation_id, limit, offset)


@router.get("/conversations/{conversation_id}/export")
def export_conversation(conversation_id: str, store: DB, context: CTX):
    with store.read_snapshot(), store.connection() as db:
        assert_active_context(db, context, minimum_role="viewer")
        conversation = _conversation(db, context, conversation_id)
        messages, size = [], 0
        for row in db.execute(
            "SELECT document FROM p_chat_messages WHERE household_id=? AND conversation_id=? ORDER BY created_at,rowid",
            (context.household_id, conversation_id),
        ):
            size += len(row[0].encode())
            if len(messages) >= MAX_EXPORT_ROWS or size > MAX_EXPORT_BYTES:
                raise PlatformError("chat_export_too_large", 413)
            messages.append(json.loads(row[0]))
        data = {
            "schema_version": 1,
            "local_only": True,
            "scope": "private_household",
            "exported_at": now().isoformat(),
            "conversation": conversation,
            "messages": messages,
            "total": len(messages),
        }
        _limited(data, MAX_EXPORT_BYTES, "chat_export_too_large")
    return JSONResponse(
        data,
        headers={
            "Content-Disposition": 'attachment; filename="argus-conversation.json"',
            "Cache-Control": "no-store",
        },
    )


@lru_cache(maxsize=1)
def calculation_catalog():
    return ToolCatalog(get_calculation_declarations())


def _command_service(store):
    from .commands import CommandService

    return CommandService(store)


def capabilities():
    from .commands import catalog

    calculations = []
    for declaration in calculation_catalog().declarations:
        schema = declaration.tool_schema()["parameters"]
        schema.get("properties", {}).pop("sources", None)
        if "required" in schema:
            schema["required"] = [
                name for name in schema["required"] if name != "sources"
            ]
        calculations.append(
            {
                "name": declaration.name,
                "description": declaration.description,
                "input_schema": schema,
            }
        )
    month = date.today().strftime("%Y-%m")
    return {
        "read_actions": list(assistant.ACTIONS),
        "record_reads": list(RECORD_RESOURCES),
        "calculations": calculations,
        "commands": [item.model_dump(mode="json") for item in catalog()],
        "model_available": configured(),
        "legacy_history_path": "/api/platform/assistant/conversations",
        "examples": [
            {
                "id": "net-worth",
                "label": {
                    "en": "Review net worth",
                    "es-419": "Revisar patrimonio neto",
                },
                "action": {"kind": "read", "action": "net_worth", "parameters": {}},
            },
            {
                "id": "spending",
                "label": {
                    "en": "Review this month's spending",
                    "es-419": "Revisar gastos de este mes",
                },
                "action": {
                    "kind": "read",
                    "action": "spending",
                    "parameters": {"month": month},
                },
            },
            {
                "id": "effective-rate",
                "label": {
                    "en": "Calculate an effective rate",
                    "es-419": "Calcular una tasa efectiva",
                },
                "action": {
                    "kind": "calculation",
                    "tool_name": "effective_rate",
                    "arguments": {
                        "nominal_rate_pct": 8,
                        "compounding_per_year": 12,
                    },
                },
            },
            {
                "id": "sample-goal",
                "label": {
                    "en": "Example: create a DOP 10,000 goal",
                    "es-419": "Ejemplo: crear una meta de DOP 10,000",
                },
                "action": {
                    "kind": "proposal",
                    "command_name": "goal.create",
                    "arguments": {
                        "name": "Sample goal / Meta de ejemplo",
                        "currency": "DOP",
                        "target_amount": "10000",
                        "monthly_contribution": "500",
                        "target_date": date(date.today().year + 1, 12, 31).isoformat(),
                    },
                },
            },
        ],
    }


@router.get("/capabilities")
def get_capabilities(context: CTX):
    return capabilities()


def owned_context(store, context, account_id=None):
    with store.read_snapshot(), store.connection() as db:
        accounts = ledger.accounts(store, context, limit=30, offset=0)["items"]
        selected = (
            ledger.account_balance(db, context.household_id, account_id)
            if account_id
            else None
        )
        records = [
            row
            for row in _command_service(store).record_choices(context)["items"]
            if row["kind"] != "memory"
        ]
        result = {
            "accounts": [
                {
                    key: account[key]
                    for key in ("id", "name", "currency", "balance", "source")
                }
                for account in accounts
            ],
            "records": records,
            "selected_account": selected,
        }
        _limited(result, 64 * 1024, "chat_context_too_large")
        return result


@router.get("/context")
def get_owned_context(store: DB, context: CTX, account_id: str | None = None):
    return {**owned_context(store, context, account_id), "current_proposal": None}


def begin_turn(store, context, request):
    encoded = _dump(request)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    with store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        prior = db.execute(
            "SELECT * FROM p_chat_turns WHERE id=?", (request.turn_id,)
        ).fetchone()
        if prior:
            if (
                prior["household_id"] != context.household_id
                or prior["payload_hash"] != digest
            ):
                raise PlatformError("turn_id_conflict", 409)
            _conversation(db, context, prior["conversation_id"], active=True)
            if prior["result_document"]:
                return {"replay": json.loads(prior["result_document"])}
            if prior["status"] == "running" and prior["lease_until"] > time():
                return {
                    "replay": FinalEvent(
                        turn_id=request.turn_id,
                        conversation_id=prior["conversation_id"],
                        status="in_progress",
                        code="turn_in_progress",
                    ).model_dump(mode="json")
                }
            conversation_id = prior["conversation_id"]
        else:
            conversation_id = request.conversation_id
            if conversation_id:
                _conversation(db, context, conversation_id, active=True)
            else:
                conversation_id = _new_conversation(
                    db, context, (request.text or "Argus")[:120]
                )["id"]
        busy = db.execute(
            "SELECT 1 FROM p_chat_turns WHERE conversation_id=? AND id!=? AND status='running' AND lease_until>?",
            (conversation_id, request.turn_id, time()),
        ).fetchone()
        if busy:
            raise PlatformError("conversation_busy", 409)
        token, stamp = identifier("attempt"), now().isoformat()
        if prior:
            db.execute(
                "UPDATE p_chat_turns SET status='running',run_token=?,lease_until=?,updated_at=? WHERE id=?",
                (token, time() + TURN_LEASE_SECONDS, stamp, request.turn_id),
            )
        else:
            db.execute(
                "INSERT INTO p_chat_turns VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    request.turn_id,
                    context.household_id,
                    conversation_id,
                    digest,
                    encoded,
                    "running",
                    token,
                    time() + TURN_LEASE_SECONDS,
                    None,
                    None,
                    stamp,
                    stamp,
                ),
            )
            _insert_message(
                db,
                context,
                conversation_id,
                _message(
                    request.turn_id,
                    role="user",
                    text=request.text,
                    code="typed_action" if request.action else "user_message",
                ),
            )
        return {
            "conversation_id": conversation_id,
            "token": token,
            "plan": json.loads(prior["plan_document"])
            if prior and prior["plan_document"]
            else None,
        }


def _running(db, context, turn_id, token):
    assert_active_context(db, context, minimum_role="viewer")
    row = db.execute(
        "SELECT * FROM p_chat_turns WHERE id=? AND household_id=? AND run_token=? AND status='running'",
        (turn_id, context.household_id, token),
    ).fetchone()
    if row is None:
        raise PlatformError("turn_no_longer_active", 409)
    _conversation(db, context, row["conversation_id"], active=True)
    return row


def checkpoint_plan(store, context, turn_id, token, plan):
    document = _limited(plan, MAX_MESSAGE_BYTES, "chat_plan_too_large")
    with store.connection(write=True) as db:
        _running(db, context, turn_id, token)
        db.execute(
            "UPDATE p_chat_turns SET plan_document=?,updated_at=? WHERE id=?",
            (document, now().isoformat(), turn_id),
        )


def settle_turn(
    store,
    context,
    turn_id,
    token,
    *,
    cards=(),
    text=None,
    code="completed",
    status="completed",
):
    with store.connection(write=True) as db:
        row = _running(db, context, turn_id, token)
        message = _message(turn_id, cards=cards, text=text, code=code)
        final = FinalEvent(
            turn_id=turn_id,
            conversation_id=row["conversation_id"],
            status=status,
            code=code,
            message=message,
        ).model_dump(mode="json")
        _insert_message(db, context, row["conversation_id"], message)
        db.execute(
            "UPDATE p_chat_turns SET status='completed',result_document=?,updated_at=? WHERE id=?",
            (_dump(final), now().isoformat(), turn_id),
        )
        return final


def mark_interrupted(store, context, turn_id, token):
    try:
        with store.connection(write=True) as db:
            _running(db, context, turn_id, token)
            db.execute(
                "UPDATE p_chat_turns SET status='interrupted',lease_until=0,updated_at=? WHERE id=?",
                (now().isoformat(), turn_id),
            )
    except PlatformError:
        pass  # Reset/deletion already removed the turn, or a newer attempt owns it.


def planning_packet(store, identity, context, request, conversation_id):
    packet = owned_context(store, context, request.account_id)
    with store.read_snapshot(), store.connection() as db:
        for mention in request.mentions:
            if mention.kind == "account":
                account = ledger.account_balance(db, context.household_id, mention.id)
                if mention.id not in {row["id"] for row in packet["accounts"]}:
                    packet["accounts"].append(
                        {
                            key: account[key]
                            for key in ("id", "name", "currency", "balance", "source")
                        }
                    )
            elif mention.id not in {row["id"] for row in packet["records"]}:
                if not mention.record_kind or mention.record_kind == "memory":
                    raise PlatformError("record_not_found", 404)
                record = _command_service(store).resolve_record(
                    context, mention.record_kind, mention.id
                )
                packet["records"].append(
                    {"id": mention.id, "kind": mention.record_kind, "record": record}
                )
        packet.update(
            {
                "message": request.text,
                "locale": request.locale,
                "explicit_currency": request.currency,
                "default_currency_hint": (
                    {"code": request.default_currency, "source": "ui_default"}
                    if request.default_currency
                    else None
                ),
                "mentions": [item.model_dump() for item in request.mentions],
                "history": transcript(store, context, conversation_id, 12)["messages"],
                "catalog": capabilities(),
                "confirmed_memories": identity.active_memories(context),
            }
        )
        current = _command_service(store).current(context, conversation_id)
        packet["current_proposal"] = current.model_dump(mode="json") if current else None
        prior = db.execute(
            "SELECT plan_document FROM p_chat_turns WHERE conversation_id=? AND plan_document IS NOT NULL ORDER BY created_at DESC,rowid DESC LIMIT 1",
            (conversation_id,),
        ).fetchone()
        packet["previous_plan"] = json.loads(prior[0]) if prior else None
    _limited(packet, MAX_CONTEXT_BYTES, "chat_context_too_large")
    return packet


def _resolve_currency(store, context, request, conversation_id, plan):
    """Ground all selected references, then make one denomination decision."""
    kind = plan["kind"]
    if kind in ("clarify", "unsupported"):
        return plan, request, False
    plan = json.loads(_dump(plan))
    values = plan.get("parameters", {}) if kind == "read" else plan.get("arguments", {})
    if kind == "records":
        values = plan
    if kind == "revise_proposal":
        values = plan["changes"]
    declared = [values.get("currency")]
    for key in ("changes", "values"):
        if isinstance(values.get(key), dict):
            declared.append(values[key].get("currency"))
    references = []
    account_id = request.account_id
    if kind == "records" and values.get("account_id"):
        if account_id and account_id != values["account_id"]:
            raise PlatformError("account_context_mismatch")
        account_id = values["account_id"]
    if account_id:
        references.append(("account", account_id))
    if kind == "records" and values.get("record_id"):
        references.append((RECORD_RESOURCES[plan["resource"]], values["record_id"]))
    if kind == "calculation" and plan.get("artifact_id"):
        history = transcript(store, context, conversation_id, 100)["messages"]
        previous = next(
            (
                card["card"]
                for message in history
                for card in message["cards"]
                if card["kind"] == "calculation"
                and card["card"]["artifact_id"] == plan["artifact_id"]
            ),
            None,
        )
        if previous is None or previous["tool_name"] != plan["tool_name"]:
            raise PlatformError("calculation_artifact_not_found", 404)
        if not values.get("currency"):
            declared.append(previous["arguments"].get("currency"))
            source = previous["arguments"].get("sources", {}).get("currency", {})
            if source.get("kind") == "account":
                references.append(("account", source["ref"]))
    service = _command_service(store)
    owned = []
    defaulted = False
    with store.read_snapshot():
        for reference_kind, record_id in dict.fromkeys(references):
            record = service.resolve_record(context, reference_kind, record_id)
            owned.append(record.get("currency"))
            if kind == "records" and record_id == values.get("record_id") and account_id:
                owner_account = (
                    record["id"]
                    if reference_kind == "account"
                    else record.get("account_id")
                )
                if owner_account and owner_account != account_id:
                    raise PlatformError("account_context_mismatch")
        currency_context = (
            {"kind": "account", "account_id": account_id, "code": request.currency}
            if account_id
            else {"kind": "explicit", "code": request.currency}
            if request.currency
            else None
        )
        if kind == "proposal":
            try:
                sources = service.inspect_currency(
                    context,
                    plan["command_name"],
                    plan["arguments"],
                    currency_context=currency_context,
                )
            except PlatformError as error:
                if (
                    error.code != "command_currency_required"
                    or not request.default_currency
                ):
                    raise
                sources = service.inspect_currency(
                    context,
                    plan["command_name"],
                    plan["arguments"],
                    currency_context={
                        "kind": "ui_default",
                        "code": request.default_currency,
                    },
                )
                defaulted = True
            owned.extend(source.code for source in sources)
        elif kind == "revise_proposal":
            previous = service.get(context, plan["proposal_id"])
            if previous.conversation_id != conversation_id:
                raise PlatformError("proposal_not_found", 404)
            sources = service.inspect_revision(
                context, plan["proposal_id"], plan["revision"], plan["changes"]
            )
            owned.extend(source.code for source in sources)
    candidates = [
        value for value in (request.currency, *declared, *owned) if value is not None
    ]
    if any(
        not isinstance(value, str) or value not in CURRENCY_DIGITS for value in candidates
    ):
        raise PlatformError("unsupported_currency")
    currencies = set(candidates)
    if len(currencies) > 1:
        raise PlatformError(
            "account_currency_mismatch"
            if any(reference[0] == "account" for reference in references)
            else "currency_context_mismatch"
        )
    if not currencies and request.default_currency:
        defaulted = True
    currency = next(iter(currencies), request.default_currency)
    if kind in ("read", "calculation") and currency is None:
        raise PlatformError("currency_required")
    if kind in ("read", "records"):
        values["currency"] = currency
    elif kind == "calculation" and not plan.get("artifact_id"):
        values["currency"] = currency
    return plan, request.model_copy(
        update={"currency": currency, "account_id": account_id}
    ), defaulted


def _read_records(store, context, request, plan):
    account_id = request.account_id
    currency = request.currency
    with store.read_snapshot(), store.connection() as db:
        if plan["resource"] == "accounts":
            record_id = plan.get("record_id") or account_id
            result = (
                {
                    "items": [
                        ledger.account_balance(db, context.household_id, record_id)
                    ],
                    "total": 1,
                }
                if record_id
                else ledger.accounts(
                    store,
                    context,
                    currency=currency,
                    limit=plan["limit"],
                    offset=plan["offset"],
                )
            )
        elif plan.get("record_id"):
            result = {
                "items": [ledger._transaction_response(db, context, plan["record_id"])],
                "total": 1,
            }
        else:
            result = ledger.list_transactions(
                store,
                context,
                account_id=account_id,
                currency=currency,
                limit=plan["limit"],
                offset=plan["offset"],
                date_from=plan.get("date_from"),
                date_to=plan.get("date_to"),
                category=plan.get("category"),
            )
    rows = []
    for record in result["items"]:
        if plan["resource"] == "accounts":
            title, amount_key, page = record["name"], "balance", "accounts"
            fields = [
                {"key": "institution", "value": record["institution"], "kind": "text"}
            ]
        else:
            title, amount_key, page = record["merchant"], "amount", "transactions"
            fields = [
                {
                    "key": key,
                    "value": record[key],
                    "kind": "date" if key == "date" else "text",
                }
                for key in ("date", "category", "status", "description")
            ]
        fields.append(
            {
                "key": amount_key,
                "value": record[amount_key],
                "kind": "money",
                "currency": record["currency"],
            }
        )
        rows.append(
            {
                "record_id": record["id"],
                "title": title,
                "fields": fields,
                "evidence": [record["source"]],
                "target": {"page": page, "record_id": record["id"]},
            }
        )
    return {
        "kind": "records",
        "resource": plan["resource"],
        "query": {**plan, "account_id": account_id, "currency": currency},
        "rows": rows,
        "total": result["total"],
        "limit": plan["limit"],
        "offset": plan["offset"],
    }


def _calculation(store, context, request, conversation_id, plan, defaulted):
    declaration = calculation_catalog().get(plan["tool_name"])
    if declaration is None:
        raise PlatformError("unknown_tool")
    arguments = dict(plan["arguments"])
    arguments.pop("sources", None)
    if plan.get("artifact_id"):
        history = transcript(store, context, conversation_id, 100)["messages"]
        previous = next(
            (
                card["card"]
                for message in history
                for card in message["cards"]
                if card["kind"] == "calculation"
                and card["card"]["artifact_id"] == plan["artifact_id"]
            ),
            None,
        )
        if previous is None or previous["tool_name"] != declaration.name:
            raise PlatformError("calculation_artifact_not_found", 404)
        try:
            arguments = declaration.recompute_arguments(
                previous["arguments"], arguments
            ).model_dump(mode="json")
        except (ValueError, ValidationError):
            raise PlatformError("invalid_calculation_edit") from None
    evidence = []
    if request.account_id:
        with store.connection() as db:
            account = ledger.account_balance(db, context.household_id, request.account_id)
        evidence = [account["source"]]
    # Provenance is server-owned, never copied from a model-created sources map.
    if "sources" in declaration.arguments_type.model_fields:
        if not plan.get("artifact_id"):
            arguments["sources"] = {key: {"kind": "user"} for key in arguments}
            if defaulted:
                arguments["sources"]["currency"] = {"kind": "assumption"}
        if request.account_id:
            arguments["sources"]["currency"] = {
                "kind": "account",
                "ref": account["id"],
                "currency": account["currency"],
                "date": account["source"]["as_of"],
            }
    call = ToolCall(
        tool_name=declaration.name, call_id=request.turn_id, arguments=arguments
    )
    outcome = declaration.invoke_sync(arguments)
    card = declaration.result_card(
        call=call, outcome=outcome, artifact_id=identifier("calculation")
    )
    return {
        "kind": "calculation",
        "card": card.model_dump(mode="json"),
        "evidence": evidence,
    }


def _prepare_execution(store, context, request, conversation_id, plan):
    with store.read_snapshot():
        plan, effective, defaulted = _resolve_currency(
            store, context, request, conversation_id, plan
        )
        if plan["kind"] == "read":
            parameters = Parameters.model_validate(
                {
                    key: value
                    for key, value in plan["parameters"].items()
                    if value is not None
                }
            )
            facts = assistant.grounded_facts(store, context, plan["action"], parameters)
            code = "grounded_records" if facts else "no_records"
            card = {
                "kind": "read",
                "action": plan["action"],
                "code": code,
                "facts": [fact.model_dump(mode="json") for fact in facts],
            }
        elif plan["kind"] == "records":
            card = _read_records(store, context, effective, plan)
            code = "grounded_records" if card["rows"] else "no_records"
        elif plan["kind"] == "calculation":
            card = _calculation(store, context, effective, conversation_id, plan, defaulted)
            code = "calculated"
        else:
            card, code = None, None
    return plan, effective, card, code, defaulted


async def run_turn(store, identity, context, request, reservation, planner, emit):
    conversation_id, token = reservation["conversation_id"], reservation["token"]

    async def plan():
        emit({"type": "stage_start", "stage": "interpret"})
        if reservation["plan"]:
            result = reservation["plan"]
        elif request.action:
            result = request.action.model_dump(mode="json")
        else:
            packet = await run_in_threadpool(
                planning_packet, store, identity, context, request, conversation_id
            )
            result = (
                await planner.plan(packet, store=store, context=context)
            ).plan.model_dump(mode="json")
        result = PlannedTurn.model_validate({"plan": result}).plan.model_dump(mode="json")
        await run_in_threadpool(
            checkpoint_plan, store, context, request.turn_id, token, result
        )
        emit({"type": "stage_outcome", "stage": "interpret", "status": "completed"})
        return result

    async def execute(plan):
        emit({"type": "stage_start", "stage": "execute"})
        plan, effective_request, card, code, defaulted = await run_in_threadpool(
            _prepare_execution, store, context, request, conversation_id, plan
        )
        kind = plan["kind"]
        if card is not None:
            final = await run_in_threadpool(
                settle_turn,
                store,
                context,
                request.turn_id,
                token,
                cards=[card],
                code=code,
            )
        elif kind in ("proposal", "revise_proposal"):

            def propose():
                completed = []

                def append(bound, captured, proposal):
                    completed.append(
                        settle_turn(
                            bound,
                            captured,
                            request.turn_id,
                            token,
                            cards=[
                                {
                                    "kind": "proposal",
                                    "proposal": proposal.model_dump(mode="json"),
                                }
                            ],
                            code="confirmation_required",
                        )
                    )

                service = _command_service(store)
                if kind == "proposal":
                    currency_context = (
                        {"kind": "account", "account_id": effective_request.account_id}
                        if effective_request.account_id
                        else {
                            "kind": "ui_default" if defaulted else "explicit",
                            "code": effective_request.currency,
                        }
                        if effective_request.currency
                        else None
                    )
                    service.prepare(
                        context,
                        plan["command_name"],
                        plan["arguments"],
                        conversation_id,
                        request.turn_id,
                        currency_context,
                        on_proposal=append,
                    )
                else:
                    original = service.get(context, plan["proposal_id"])
                    if original.conversation_id != conversation_id:
                        raise PlatformError("proposal_not_found", 404)
                    service.revise(
                        context,
                        plan["proposal_id"],
                        plan["revision"],
                        plan["changes"],
                        request_id=request.turn_id,
                        on_proposal=append,
                    )
                if not completed:
                    raise PlatformError("proposal_turn_conflict", 409)
                return completed[0]

            final = await run_in_threadpool(propose)
        else:
            final = await run_in_threadpool(
                settle_turn,
                store,
                context,
                request.turn_id,
                token,
                text=plan.get("question") if kind == "clarify" else None,
                code="clarification_required" if kind == "clarify" else "unsupported",
            )
        emit({"type": "stage_outcome", "stage": "execute", "status": "completed"})
        return final

    try:
        with tracing_context(enabled=False):
            return await run_conversation_graph(
                plan,
                {
                    kind: execute
                    for kind in PlannedTurn.model_json_schema()["properties"]["plan"][
                        "discriminator"
                    ]["mapping"]
                },
            )
    except asyncio.CancelledError:
        await asyncio.shield(
            run_in_threadpool(mark_interrupted, store, context, request.turn_id, token)
        )
        raise
    except ModelUnavailable:
        return await run_in_threadpool(
            _failed_turn,
            store,
            context,
            request.turn_id,
            token,
            conversation_id,
            "model_unavailable",
            "model_unavailable",
        )
    except (PlatformError, ValidationError) as error:
        code = error.code if isinstance(error, PlatformError) else "invalid_plan"
        return await run_in_threadpool(
            _failed_turn,
            store,
            context,
            request.turn_id,
            token,
            conversation_id,
            code,
            "failed",
        )
    except Exception:
        return await run_in_threadpool(
            _failed_turn,
            store,
            context,
            request.turn_id,
            token,
            conversation_id,
            "chat_unavailable",
            "failed",
        )


def _failed_turn(store, context, turn_id, token, conversation_id, code, status):
    try:
        return settle_turn(store, context, turn_id, token, code=code, status=status)
    except PlatformError as current:
        return FinalEvent(
            turn_id=turn_id,
            conversation_id=conversation_id,
            code=current.code,
            status="failed",
        ).model_dump(mode="json")


@router.post("/turn")
async def submit_turn(payload: TurnRequest, request: Request, store: DB, context: CTX):
    reservation = await run_in_threadpool(begin_turn, store, context, payload)

    async def events():
        if "replay" in reservation:
            yield "data: " + _dump(reservation["replay"]) + "\n\n"
            yield "data: [DONE]\n\n"
            return
        queue = asyncio.Queue()
        planner = (
            getattr(request.app.state, "chat_planner", None) or LocalStructuredPlanner()
        )
        task = asyncio.create_task(
            run_turn(
                store,
                request.app.state.identity,
                context,
                payload,
                reservation,
                planner,
                queue.put_nowait,
            )
        )
        pending = None
        try:
            while not task.done():
                pending = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait(
                    {pending, task}, return_when=asyncio.FIRST_COMPLETED
                )
                if pending in done:
                    yield "data: " + _dump(pending.result()) + "\n\n"
                else:
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
            while not queue.empty():
                yield "data: " + _dump(queue.get_nowait()) + "\n\n"
            yield "data: " + _dump(await task) + "\n\n"
            yield "data: [DONE]\n\n"
        finally:
            if pending is not None and not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _append_proposal_event(bound, context, proposal, *, code):
    with bound.connection(write=True) as db:
        assert_active_context(db, context)
        _conversation(db, context, proposal.conversation_id, active=True)
        message = _message(
            identifier("proposal-event"),
            code=code,
            cards=[{"kind": "proposal", "proposal": proposal.model_dump(mode="json")}],
        )
        _insert_message(db, context, proposal.conversation_id, message)
        return message


@router.patch("/proposals/{proposal_id}")
def patch_proposal(proposal_id: str, payload: PatchProposal, store: DB, context: CTX):
    appended = []
    proposal = _command_service(store).revise(
        context,
        proposal_id,
        payload.expected_revision,
        payload.changes,
        request_id=payload.request_id,
        on_proposal=lambda bound, captured, item: appended.append(
            _append_proposal_event(bound, captured, item, code="proposal_revised")
        ),
    )
    return {
        "proposal": proposal.model_dump(mode="json"),
        "message": appended[0] if appended else None,
    }


@router.post("/proposals/{proposal_id}/confirm")
def confirm_proposal(proposal_id: str, payload: ConfirmProposal, store: DB, context: CTX):
    appended = []

    def append(bound, captured, receipt):
        with bound.connection(write=True) as db:
            assert_active_context(db, captured)
            _conversation(db, captured, receipt.conversation_id, active=True)
            message = _message(
                "receipt:" + receipt.receipt_id,
                code="command_completed",
                cards=[{"kind": "receipt", "receipt": receipt.model_dump(mode="json")}],
            )
            _insert_message(db, captured, receipt.conversation_id, message)
            appended.append(message)

    receipt = _command_service(store).confirm(
        context, proposal_id, payload.expected_revision, on_receipt=append
    )
    if not appended:
        with store.connection() as db:
            row = db.execute(
                "SELECT document FROM p_chat_messages WHERE household_id=? AND turn_id=? AND role='assistant'",
                (context.household_id, "receipt:" + receipt.receipt_id),
            ).fetchone()
            if row:
                appended.append(json.loads(row[0]))
    return {
        "receipt": receipt.model_dump(mode="json"),
        "message": appended[0] if appended else None,
    }


@router.post("/proposals/{proposal_id}/cancel")
def cancel_proposal(proposal_id: str, payload: CancelProposal, store: DB, context: CTX):
    proposal = _command_service(store).cancel(
        context, proposal_id, payload.expected_revision
    )
    return {"proposal": proposal.model_dump(mode="json"), "message": None}


def export_data(db, context):
    result, total = {}, 0
    for key in ("conversations", "turns", "messages"):
        rows = []
        for row in db.execute(
            f"SELECT * FROM p_chat_{key} WHERE household_id=? ORDER BY rowid",
            (context.household_id,),
        ):
            total += len(_dump(dict(row)).encode())
            if len(rows) >= MAX_EXPORT_ROWS or total > MAX_EXPORT_BYTES:
                raise PlatformError("chat_export_too_large", 413)
            rows.append(dict(row))
        result[key] = rows
    return result


def clear_data(db, context):
    for table in ("p_chat_messages", "p_chat_turns", "p_chat_conversations"):
        db.execute(f"DELETE FROM {table} WHERE household_id=?", (context.household_id,))


def trash_all_conversations(db, context):
    """Use the caller's household history transaction; all rows remain restorable."""
    assert_active_context(db, context, minimum_role="owner")
    return db.execute(
        "UPDATE p_chat_conversations SET state='trashed',updated_at=? WHERE household_id=? AND state!='trashed'",
        (now().isoformat(), context.household_id),
    ).rowcount


def usage_data(db, context):
    return {
        key: db.execute(
            f"SELECT COUNT(*) FROM p_chat_{key} WHERE household_id=?",
            (context.household_id,),
        ).fetchone()[0]
        for key in ("conversations", "messages")
    }


def register_identity(identity):
    identity.register_data_domain(
        "chat", export=export_data, clear=clear_data, usage=usage_data
    )
