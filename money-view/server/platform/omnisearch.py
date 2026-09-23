"""Bounded literal-prefix recall over canonical household records, without a text copy.

Field indexes order candidates identically to the merge. Empty-query recall uses
recording-date indexes. Neither path scans or counts the whole household ledger.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from ..store import Store
from .common import Context, Evidence, Model, decimal_amount, get_context, get_store
from .ledger import active_transaction_predicate

Kind = Literal[
    "all",
    "conversation",
    "account",
    "transaction",
    "budget",
    "goal",
    "scenario",
    "holding",
    "deposit",
]
Scope = Literal["all", "recent", "pinned"]
Page = Literal[
    "accounts",
    "transactions",
    "budgets",
    "goals",
    "scenarios",
    "investments",
    "deposits",
    "saved",
    "chat",
]
DB = Annotated[Store, Depends(get_store)]
CTX = Annotated[Context, Depends(get_context)]
router = APIRouter(prefix="/api/platform")
DEPOSIT_WINDOW = 500
TRANSACTION_WINDOW = 1041  # Maximum supported offset + page size + lookahead.


class Target(Model):
    page: Page
    record_id: str
    conversation_id: str | None = None
    account_id: str | None = None
    decision: str | None = None


class PreviewField(Model):
    label: str
    value: str = Field(max_length=240)


class SearchItem(Model):
    id: str
    kind: Kind
    title: str = Field(max_length=160)
    preview: str = Field(max_length=400)
    recorded_at: str | None
    as_of: str | None
    pinned: bool
    target: Target
    fields: list[PreviewField]
    evidence: Evidence | None = None


class SearchResult(Model):
    items: list[SearchItem]
    has_more: bool
    next_offset: int | None
    match_mode: Literal["field_prefix"] = "field_prefix"
    query: str
    kind: Kind
    scope: Scope
    deposit_window: int = DEPOSIT_WINDOW
    window_limited: bool = False


@dataclass(frozen=True)
class Source:
    kind: str
    table: str
    page: str
    active: str
    title: str
    fields: tuple[tuple[str, str], ...]
    date: str
    as_of: str
    preview: str = "''"
    pinned: str = "0"
    evidence: str = "NULL"
    source_kind: str = "'user'"
    account: str = "NULL"

    @property
    def prefix(self):
        return f"p_omni_{self.table.removeprefix('p_')}_{self.kind}"


def j(path):
    return f"json_extract(document,'$.{path}')"


SOURCES = (
    Source(
        "conversation",
        "p_chat_conversations",
        "chat",
        "state='active'",
        "title",
        (("title", "title"),),
        "updated_at",
        "substr(updated_at,1,10)",
        pinned="pinned",
    ),
    Source(
        "conversation",
        "p_assistant_conversations",
        "saved",
        "state='active'",
        "title",
        (("title", "title"),),
        "updated_at",
        "substr(updated_at,1,10)",
        pinned="0",
    ),
    Source(
        "account",
        "p_accounts",
        "accounts",
        "deleted_at IS NULL",
        "name",
        (("name", "name"), ("institution", "institution")),
        "recorded_at",
        "as_of",
        preview="institution",
        source_kind="source_kind",
        account="id",
    ),
    Source(
        "transaction",
        "p_transactions",
        "transactions",
        "deleted_at IS NULL",
        "merchant",
        (
            ("merchant", "merchant"),
            ("description", "description"),
            ("category", "category"),
            ("notes", "notes"),
        ),
        "recorded_at",
        "date",
        preview="description",
        source_kind="source_kind",
        account="account_id",
    ),
    Source(
        "budget",
        "p_plans",
        "budgets",
        "kind='budget' AND status!='archived'",
        j("category"),
        (("category", j("category")), ("month", j("month"))),
        "recorded_at",
        j("evidence.as_of"),
        evidence=j("evidence"),
    ),
    Source(
        "goal",
        "p_plans",
        "goals",
        "kind='goal' AND status!='archived'",
        j("name"),
        (("name", j("name")),),
        "recorded_at",
        j("evidence.as_of"),
        evidence=j("evidence"),
    ),
    Source(
        "scenario",
        "p_scenarios",
        "scenarios",
        "1",
        j("name"),
        (("name", j("name")), ("template", j("template"))),
        j("evidence.recorded_at"),
        j("evidence.as_of"),
        preview=j("template"),
        evidence=j("evidence"),
    ),
    Source(
        "holding",
        "p_investment_holdings",
        "investments",
        "deleted_at IS NULL",
        "name",
        (("name", "name"), ("symbol", "symbol")),
        "updated_at",
        "as_of",
        preview="symbol",
        evidence="source_json",
    ),
)

# Only user-facing, explicitly named values leave storage. Arbitrary documents,
# household/user IDs, and notes outside the selected preview never leave it.
DETAILS = {
    "conversation": (),
    "account": (
        ("institution", "institution"),
        ("currency", "currency"),
        ("account_kind", "kind"),
    ),
    "transaction": (
        ("currency", "currency"),
        ("amount_minor", "amount_minor"),
        ("category", "category"),
        ("status", "status"),
        ("notes", "notes"),
    ),
    "budget": (("currency", j("currency")), ("limit", j("limit")), ("month", j("month"))),
    "goal": (
        ("currency", j("currency")),
        ("target_amount", j("target_amount")),
        ("target_date", j("target_date")),
    ),
    "scenario": (
        ("currency", j("inputs.currency")),
        ("initial_balance", j("inputs.initial_balance")),
        ("template", j("template")),
    ),
    "holding": (
        ("currency", "currency"),
        ("symbol", "symbol"),
        ("quantity", "quantity"),
        ("cost_basis_minor", "total_cost_minor"),
    ),
}


def fold(value):
    return value.translate(
        str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
    )


def _tables(db):
    return {
        row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def initialize(store):
    """Indexes on source fields only; there is no separately synchronized record."""
    with store.connection(write=True) as db:
        existing = _tables(db)
        for source in SOURCES:
            if source.table not in existing:
                continue
            where = f" WHERE {source.active}" if source.active != "1" else ""
            for index, (_, field) in enumerate(source.fields):
                field = f"substr({field},1,512)"
                if source.kind == "conversation" and source.pinned != "0":
                    db.execute(
                        f"CREATE INDEX IF NOT EXISTS {source.prefix}_field{index}_pinned ON {source.table}(household_id,{field} COLLATE NOCASE,id) WHERE {source.active} AND {source.pinned}=1"
                    )
                db.execute(
                    f"CREATE INDEX IF NOT EXISTS {source.prefix}_field{index} ON {source.table}(household_id,{field} COLLATE NOCASE,id){where}"
                )
            db.execute(
                f"CREATE INDEX IF NOT EXISTS {source.prefix}_recent ON {source.table}(household_id,{source.date} DESC,id DESC){where}"
            )
            if source.kind == "conversation" and source.pinned != "0":
                db.execute(
                    f"CREATE INDEX IF NOT EXISTS {source.prefix}_pinned ON {source.table}(household_id,{source.date} DESC,id DESC) WHERE {source.active} AND {source.pinned}=1"
                )
        if "p_placement_comparisons" in existing:
            db.execute(
                "CREATE INDEX IF NOT EXISTS p_omni_deposit_owner ON p_placement_comparisons(household_id,id)"
            )


def _projection(source, match):
    details = ",".join(
        f"substr(CAST({field} AS TEXT),1,240) AS detail_{label}"
        for label, field in DETAILS[source.kind]
    )
    return f"""id,substr({source.title},1,160) AS title,substr({source.preview},1,400) AS preview,
        {source.date} AS recorded_at,{source.as_of} AS as_of,{source.pinned} AS pinned,
        {source.account} AS account_id,{source.source_kind} AS source_kind,
        CASE WHEN length({source.evidence})<=8000 THEN {source.evidence} ELSE NULL END AS evidence,
        substr({match},1,512) AS match_key{"," + details if details else ""}"""


@dataclass
class SourceWindow:
    rows: list
    limited: bool = False


def _read_source(db, source, household, query, cap, scope):
    pinned = f" AND {source.pinned}=1" if scope == "pinned" else ""
    windows = []
    if query:
        for index, (_, field) in enumerate(source.fields):
            field = f"substr({field},1,512)"
            index_name = f"{source.prefix}_field{index}" + (
                "_pinned" if scope == "pinned" else ""
            )
            windows.append(
                (
                    field,
                    index_name,
                    f" AND {field} COLLATE NOCASE>=? AND {field} COLLATE NOCASE<?",
                    (query, query + "\U0010ffff"),
                    f"{field} COLLATE NOCASE,id",
                )
            )
    else:
        windows.append(
            (
                source.date,
                f"{source.prefix}_{'pinned' if scope == 'pinned' else 'recent'}",
                "",
                (),
                f"{source.date} DESC,id DESC",
            )
        )
    result = SourceWindow([])
    for field, index_name, match, values, ordering in windows:
        selection = f"FROM {source.table} INDEXED BY {index_name} WHERE household_id=? AND {source.active}{pinned}{match} ORDER BY {ordering} LIMIT ?"
        if source.kind != "transaction":
            result.rows.extend(
                db.execute(
                    f"SELECT {_projection(source, field)} {selection}",
                    (household, *values, cap),
                )
            )
            continue
        # A fixed candidate window keeps offsets stable and caps archived-parent
        # probes. CROSS JOIN preserves candidate-first primary-key lookups.
        # Only IDs cross this boundary; projection follows visibility.
        ids = [
            row[0]
            for row in db.execute(
                f"SELECT id {selection}", (household, *values, TRANSACTION_WINDOW + 1)
            )
        ]
        result.limited |= len(ids) > TRANSACTION_WINDOW
        result.rows.extend(
            db.execute(
                f"""WITH candidates AS MATERIALIZED (SELECT value AS candidate_id FROM json_each(?))
            SELECT {_projection(source, field)} FROM candidates
            CROSS JOIN {source.table}
            WHERE {source.table}.id=candidates.candidate_id AND household_id=? AND {active_transaction_predicate(source.table)}
            ORDER BY {ordering} LIMIT ?""",
                (json.dumps(ids[:TRANSACTION_WINDOW]), household, cap),
            )
        )
    return result


def _evidence(source, row):
    if row["evidence"]:
        parsed = Evidence.model_validate_json(row["evidence"])
        return parsed.model_copy(
            update={
                "title": parsed.title[:240],
                "method": parsed.method[:400] if parsed.method else None,
                "inputs": parsed.inputs[:20],
                "url": None,
            }
        )
    if source.kind in ("account", "transaction"):
        return Evidence(
            id=f"record-{row['id']}",
            kind=row["source_kind"],
            title="Recorded source value",
            as_of=row["as_of"],
            recorded_at=row["recorded_at"],
        )
    return None


def _item(db, source, row, household):
    fields = []
    for label, _ in DETAILS[source.kind]:
        value = row[f"detail_{label}"]
        if value is None:
            continue
        if label.endswith("_minor"):
            value = decimal_amount(int(value), row["detail_currency"])
            label = label.removesuffix("_minor")
        fields.append(PreviewField(label=label, value=value))
    preview = row["preview"] or ""
    if source.kind == "conversation":
        message_table = (
            "p_chat_messages"
            if source.table == "p_chat_conversations"
            else "p_assistant_messages"
        )
        message = db.execute(
            f"SELECT substr(json_extract(document,'$.text'),1,400) FROM {message_table} WHERE household_id=? AND conversation_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
            (household, row["id"]),
        ).fetchone()
        if message and message[0]:
            preview = message[0]
    return SearchItem(
        id=f"{source.table}:{row['id']}",
        kind=source.kind,
        title=row["title"] or source.kind,
        preview=preview,
        recorded_at=row["recorded_at"],
        as_of=row["as_of"],
        pinned=bool(row["pinned"]),
        target=Target(
            page=source.page,
            record_id=row["id"],
            conversation_id=row["id"] if source.kind == "conversation" else None,
            account_id=row["account_id"],
        ),
        fields=fields,
        evidence=_evidence(source, row),
    )


def _deposits(db, household, query):
    # Ownership lives outside the immutable comparison document. Bound that join
    # explicitly rather than silently turning it into an unbounded JSON scan.
    candidates = db.execute(
        """WITH owned AS MATERIALIZED (
        SELECT id FROM p_placement_comparisons INDEXED BY p_omni_deposit_owner WHERE household_id=? ORDER BY id LIMIT ?)
        SELECT sd.id,sd.created_at,substr(json_extract(c.document,'$.inputs.country'),1,80) AS country,
            substr(json_extract(c.document,'$.inputs.currency'),1,3) AS currency,
            substr(json_extract(c.document,'$.inputs.amount'),1,80) AS amount
        FROM owned JOIN saved_decisions sd ON sd.comparison_id=owned.id JOIN comparisons c ON c.id=owned.id""",
        (household, DEPOSIT_WINDOW),
    )
    for row in candidates:
        words = [row["country"] or "", row["currency"] or ""]
        matches = [word for word in words if fold(word).startswith(fold(query))]
        if query and not matches:
            continue
        item = SearchItem(
            id=f"deposit:{row['id']}",
            kind="deposit",
            title=" · ".join(words),
            preview="",
            recorded_at=row["created_at"],
            as_of=row["created_at"][:10],
            pinned=False,
            target=Target(page="deposits", record_id=row["id"], decision=row["id"]),
            fields=[
                PreviewField(label="country", value=words[0]),
                PreviewField(label="currency", value=words[1]),
            ],
        )
        yield min(fold(word) for word in matches) if query else row["created_at"], item


def search_records(store, context, *, q="", kind="all", scope="all", limit=20, offset=0):
    query = q.strip()
    cap = offset + limit + 1
    candidates = {}
    window_limited = False
    with store.connection() as db:
        existing = _tables(db)
        for source in SOURCES:
            if (
                source.table not in existing
                or (kind != "all" and source.kind != kind)
                or (scope != "all" and source.kind != "conversation")
            ):
                continue
            if scope == "pinned" and source.pinned == "0":
                continue
            window = _read_source(db, source, context.household_id, query, cap, scope)
            window_limited |= window.limited
            for row in window.rows:
                item_id = f"{source.table}:{row['id']}"
                key = (
                    fold(row["match_key"] or "") if query else (row["recorded_at"] or "")
                )
                previous = candidates.get(item_id)
                if previous is None or (query and key < previous[0]):
                    candidates[item_id] = (key, source, row)
        # Only project the bounded final window; conversation dossiers use indexed reads.
        ranked = [
            (key, item_id, source, row)
            for item_id, (key, source, row) in candidates.items()
        ]
        ranked.sort(key=lambda value: (value[0], value[1]), reverse=not bool(query))
        items = [
            (key, _item(db, source, row, context.household_id))
            for key, _, source, row in ranked[:cap]
        ]
        if (
            scope == "all"
            and kind in ("all", "deposit")
            and "p_placement_comparisons" in existing
        ):
            items.extend(_deposits(db, context.household_id, query))
    items.sort(key=lambda value: (value[0], value[1].id), reverse=not bool(query))
    has_more = len(items) > offset + limit
    return SearchResult(
        items=[item for _, item in items[offset : offset + limit]],
        has_more=has_more,
        next_offset=offset + limit if has_more and offset + limit <= 1000 else None,
        window_limited=window_limited or (has_more and offset + limit > 1000),
        query=query,
        kind=kind,
        scope=scope,
    )


@router.get("/search", response_model=SearchResult)
def search(
    *,
    store: DB,
    context: CTX,
    q: Annotated[str, Query(max_length=120)] = "",
    kind: Kind = "all",
    scope: Scope = "all",
    limit: Annotated[int, Query(ge=1, le=40)] = 20,
    offset: Annotated[int, Query(ge=0, le=1000)] = 0,
):
    return search_records(
        store, context, q=q, kind=kind, scope=scope, limit=limit, offset=offset
    )
