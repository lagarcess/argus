from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import tempfile
import unicodedata
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from faker import Faker

from tests.synthetic_ingestion.extract import FIELDS
from tests.synthetic_ingestion.factories import build_corpus
from tests.synthetic_ingestion.harness import Harness, field_issues

SECRET = "synthetic-session-token-not-a-real-secret"
MATCH_WINDOW_DAYS = 3
INFORMATIONAL = ("identity_derived", "reversal_linked")
OPEN = ("proposed", "pending", "revision")

PENDING_CONSENT = "pending_consent"
MFA_REQUIRED = "mfa_required"
ACTIVE = "active"
DEGRADED = "degraded"
REAUTH_REQUIRED = "reauth_required"
CANCELLED = "cancelled"
REVOKED = "revoked"

TRANSITIONS = {
    (PENDING_CONSENT, "mfa_challenge"): MFA_REQUIRED,
    (PENDING_CONSENT, "authenticated"): ACTIVE,
    (MFA_REQUIRED, "authenticated"): ACTIVE,
    (MFA_REQUIRED, "cancelled"): CANCELLED,
    (ACTIVE, "refresh_ok"): ACTIVE,
    (ACTIVE, "source_failed"): DEGRADED,
    (ACTIVE, "parse_error"): DEGRADED,
    (ACTIVE, "session_expired"): REAUTH_REQUIRED,
    (ACTIVE, "mfa_challenge"): REAUTH_REQUIRED,
    (DEGRADED, "refresh_ok"): ACTIVE,
    (DEGRADED, "source_failed"): DEGRADED,
    (DEGRADED, "parse_error"): DEGRADED,
    (DEGRADED, "session_expired"): REAUTH_REQUIRED,
    (DEGRADED, "mfa_challenge"): REAUTH_REQUIRED,
    (REAUTH_REQUIRED, "authenticated"): ACTIVE,
    (REAUTH_REQUIRED, "cancelled"): REAUTH_REQUIRED,
}


class IllegalTransition(Exception):
    pass


class BatchRejected(Exception):
    pass


@dataclass(frozen=True)
class SourceAccount:
    source_id: str
    name: str
    currency: str


@dataclass(frozen=True)
class Txn:
    account: str
    booked: str
    amount: str
    direction: str
    currency: str
    description: str
    institution_id: str | None = None
    pending: bool = False
    pending_ref: str | None = None
    reverses_ref: str | None = None
    reference: str | None = None


@dataclass(frozen=True)
class Balance:
    account: str
    as_of: str
    amount: str
    currency: str


@dataclass(frozen=True)
class Refresh:
    at: str
    failure: str | None = None
    accounts: tuple[SourceAccount, ...] = ()
    balances: tuple[Balance, ...] = ()
    txns: tuple[Txn, ...] = ()
    coverage: tuple[str, str] | None = None


class Store:
    def __init__(self) -> None:
        self.connections: dict[str, dict] = {}
        self.accounts: dict[str, dict] = {}
        self.observations: dict[str, dict] = {}
        self.proposals: dict[str, dict] = {}
        self.records: dict[str, dict] = {}
        self.snapshots: list[dict] = []
        self.balance_checks: list[dict] = []
        self.account_links: list[dict] = []
        self.events: list[dict] = []
        self.vault: dict[str, str] = {}
        self._ids = 0

    def new_id(self, prefix: str) -> str:
        self._ids += 1
        return f"{prefix}-{self._ids:04d}"

    def without_vault(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "vault"}


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(plain.casefold().split())


def observation_key(connection_id: str, txn: Txn, occurrence: int) -> str:
    if txn.institution_id:
        return f"id:{connection_id}:{txn.account}:{txn.institution_id}"
    return (
        f"fp:{connection_id}:{txn.account}:{txn.booked}|{txn.direction}|{txn.amount}"
        f"|{txn.currency}|{occurrence}|{_norm(txn.description)}"
    )


def _scope(key: str) -> tuple[str, str]:
    _, connection_id, source_account, _ = key.split(":", 3)
    return connection_id, source_account


def _days(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def _record_keys(record: dict) -> list[str]:
    return [key for source in record["provenance"] for key in source.get("keys", [])]


def _record_side(record: dict, account: str) -> str | None:
    fields = record["fields"]
    if fields["account"] == account:
        return "credit" if fields["kind"] in ("income", "refund") else "debit"
    if record.get("counterpart") == account:
        return "credit"
    return None


def blocking(proposal: dict) -> list[str]:
    return [i for i in proposal["issues"] if i.split(":")[0] not in INFORMATIONAL]


def _owned(store: Store, actor: str, connection_id: str) -> dict:
    connection = store.connections[connection_id]
    if connection["owner"] != actor:
        raise PermissionError("only the consenting owner operates a connection")
    return connection


def _move(connection: dict, event: str) -> None:
    transition = (connection["state"], event)
    if transition not in TRANSITIONS:
        raise IllegalTransition(f"{connection['state']} does not accept {event}")
    connection["state"] = TRANSITIONS[transition]


def _drop_secret(store: Store, connection: dict) -> None:
    store.vault.pop(connection["vault_handle"] or "", None)
    connection["vault_handle"] = None


def connect(
    store: Store, owner: str, method: str, selected: dict, secret: str | None = None
) -> str:
    connection_id = store.new_id("conn")
    handle = None
    if secret is not None:
        handle = store.new_id("vault")
        store.vault[handle] = secret
    store.connections[connection_id] = {
        "id": connection_id,
        "owner": owner,
        "method": method,
        "state": PENDING_CONSENT,
        "selected": dict(selected),
        "declined": [],
        "account_map": {},
        "names": {},
        "vault_handle": handle,
        "history_from": None,
        "coverage": None,
        "last_attempt_at": None,
        "last_success_at": None,
        "last_error": None,
        "refreshed": False,
    }
    store.events.append({"code": "connection_created", "connection": connection_id})
    return connection_id


def authenticate(store: Store, actor: str, connection_id: str, outcome: str) -> str:
    connection = _owned(store, actor, connection_id)
    _move(connection, outcome)
    if connection["state"] == CANCELLED:
        _drop_secret(store, connection)
    store.events.append(
        {"code": outcome, "connection": connection_id, "state": connection["state"]}
    )
    return connection["state"]


def refresh(store: Store, actor: str, connection_id: str, result: Refresh) -> dict:
    connection = _owned(store, actor, connection_id)
    if connection["state"] not in (ACTIVE, DEGRADED):
        raise IllegalTransition(f"{connection['state']} cannot refresh")
    connection["last_attempt_at"] = result.at
    if result.failure:
        _move(connection, result.failure)
        connection["last_error"] = result.failure
        store.events.append(
            {"code": result.failure, "connection": connection_id, "applied": False}
        )
        return {"applied": False, "state": connection["state"]}
    staged = deepcopy(store)
    try:
        summary = _apply(staged, staged.connections[connection_id], result)
    except BatchRejected:
        _move(connection, "parse_error")
        connection["last_error"] = "parse_error"
        store.events.append(
            {"code": "batch_rejected", "connection": connection_id, "applied": False}
        )
        return {"applied": False, "state": connection["state"]}
    store.__dict__.update(staged.__dict__)
    connection = store.connections[connection_id]
    _move(connection, "refresh_ok")
    connection["last_success_at"] = result.at
    connection["last_error"] = None
    store.events.append({"code": "refresh_ok", "connection": connection_id, **summary})
    return {"applied": True, "state": connection["state"], **summary}


def _parse(result: Refresh) -> None:
    for txn in result.txns:
        probe = {
            "source_id": "boundary-probe",
            "date": txn.booked,
            "description": txn.description or "-",
            "amount": txn.amount,
            "currency": txn.currency,
            "kind": "expense",
            "account": txn.account,
            "destination": "personal",
        }
        if field_issues(probe) or txn.direction not in ("debit", "credit"):
            raise BatchRejected("parse_error")
    for balance in result.balances:
        if (
            balance.currency not in ("DOP", "USD")
            or not Decimal(balance.amount).is_finite()
        ):
            raise BatchRejected("parse_error")


def _apply(store: Store, connection: dict, result: Refresh) -> dict:
    _parse(result)
    summary = {
        "new_proposals": 0,
        "seen": 0,
        "revisions": 0,
        "missing": 0,
        "discarded_unconsented": 0,
        "new_source_accounts": 0,
    }
    first = not connection["refreshed"]
    for account in result.accounts:
        source_id = account.source_id
        if source_id in connection["account_map"]:
            if connection["names"][source_id] != account.name:
                connection["names"][source_id] = account.name
                store.events.append(
                    {"code": "source_account_renamed", "connection": connection["id"]}
                )
        elif first and source_id in connection["selected"]:
            argus_id = connection["selected"][source_id]
            if argus_id is None:
                argus_id = store.new_id("acct")
                store.accounts[argus_id] = {
                    "owner": connection["owner"],
                    "name": account.name,
                    "currency": account.currency,
                }
            connection["account_map"][source_id] = argus_id
            connection["names"][source_id] = account.name
        elif first:
            connection["declined"].append(source_id)
        elif source_id not in connection["declined"] and not any(
            link["source_id"] == source_id for link in store.account_links
        ):
            store.account_links.append(
                {
                    "connection": connection["id"],
                    "source_id": source_id,
                    "currency": account.currency,
                    "status": "needs_owner_decision",
                }
            )
            summary["new_source_accounts"] += 1
    connection["refreshed"] = True
    mapped = connection["account_map"]
    for balance in result.balances:
        if balance.account in mapped:
            store.snapshots.append(
                {
                    "connection": connection["id"],
                    "account": mapped[balance.account],
                    "as_of": balance.as_of,
                    "amount": balance.amount,
                    "currency": balance.currency,
                }
            )
    occurrences: dict[tuple, int] = {}
    seen: set[str] = set()
    for txn in result.txns:
        if txn.account not in mapped:
            summary["discarded_unconsented"] += 1
            continue
        base = (
            txn.account,
            txn.booked,
            txn.direction,
            txn.amount,
            txn.currency,
            _norm(txn.description),
        )
        occurrence = occurrences.get(base, 0)
        occurrences[base] = occurrence + 1
        key = observation_key(connection["id"], txn, occurrence)
        seen.add(key)
        known = store.observations.get(key)
        if known is None:
            store.observations[key] = {"connection": connection["id"], "txn": asdict(txn)}
            _propose(store, connection, key, txn)
            summary["new_proposals"] += 1
        elif known["txn"] == asdict(txn):
            summary["seen"] += 1
        else:
            summary["revisions"] += _revise(store, connection, key, known["txn"], txn)
            known["txn"] = asdict(txn)
    _pair_transfers(store, connection["owner"])
    if result.coverage:
        summary["missing"] = _mark_missing(store, connection, result.coverage, seen)
        connection["coverage"] = list(result.coverage)
        start = result.coverage[0]
        if connection["history_from"] is None or start < connection["history_from"]:
            connection["history_from"] = start
    for proposal in store.proposals.values():
        _refresh_issues(store, proposal)
    return summary


def _holder(store: Store, key: str) -> str | None:
    for record in store.records.values():
        if key in _record_keys(record):
            return record["id"]
    for proposal in store.proposals.values():
        if key in proposal["keys"] and proposal["status"] in ("proposed", "pending"):
            return proposal["id"]
    return None


def _propose(store: Store, connection: dict, key: str, txn: Txn) -> str:
    fields = {
        "source_id": key,
        "date": txn.booked,
        "description": txn.description,
        "amount": txn.amount,
        "currency": txn.currency,
        "kind": "expense" if txn.direction == "debit" else "",
        "account": connection["account_map"][txn.account],
        "destination": "personal",
    }
    proposal = {
        "id": store.new_id("prop"),
        "owner": connection["owner"],
        "connection": connection["id"],
        "keys": [key],
        "direction": txn.direction,
        "status": "pending" if txn.pending else "proposed",
        "fields": fields,
        "counterpart": None,
        "notes": [],
        "acknowledged": [],
        "cross_currency": [],
        "issues": [],
        "reference": txn.reference,
    }
    if txn.pending_ref:
        pending_key = f"id:{connection['id']}:{txn.account}:{txn.pending_ref}"
        for other in store.proposals.values():
            if pending_key in other["keys"] and other["status"] == "pending":
                other["status"] = "superseded"
                proposal["notes"].append(f"replaces_pending:{other['id']}")
    if txn.reverses_ref:
        original = _holder(
            store, f"id:{connection['id']}:{txn.account}:{txn.reverses_ref}"
        )
        if original:
            fields["kind"] = "refund"
            proposal["notes"].append(f"reverses:{original}")
    store.proposals[proposal["id"]] = proposal
    return proposal["id"]


def _revise(store: Store, connection: dict, key: str, before: dict, txn: Txn) -> int:
    changed = {
        name: value
        for name, source, value in (
            ("date", "booked", txn.booked),
            ("amount", "amount", txn.amount),
            ("description", "description", txn.description),
        )
        if before[source] != value
    }
    holder = _holder(store, key)
    if holder in store.records:
        record = store.records[holder]
        changes = {k: v for k, v in changed.items() if k not in record["user_fields"]}
        if not changes:
            return 0
        revision_id = store.new_id("prop")
        store.proposals[revision_id] = {
            "id": revision_id,
            "owner": connection["owner"],
            "connection": connection["id"],
            "keys": [key],
            "direction": txn.direction,
            "status": "revision",
            "record": holder,
            "changes": changes,
            "fields": dict(record["fields"]),
            "counterpart": record.get("counterpart"),
            "notes": [],
            "acknowledged": [],
            "cross_currency": [],
            "issues": [],
            "reference": txn.reference,
        }
        return 1
    if holder in store.proposals:
        store.proposals[holder]["fields"].update(changed)
        store.proposals[holder]["notes"].append("source_updated_before_review")
        return 1
    return 0


def _pair_transfers(store: Store, owner: str) -> None:
    candidates = [
        p
        for p in store.proposals.values()
        if p["owner"] == owner
        and p["status"] == "proposed"
        and p["counterpart"] is None
        and len(p["keys"]) == 1
        and not any(n.startswith("reverses:") for n in p["notes"])
        and "pair_rejected" not in p["notes"]
    ]
    debits = [p for p in candidates if p["direction"] == "debit"]
    credits = [p for p in candidates if p["direction"] == "credit"]
    merged: set[str] = set()
    for debit in debits:
        for credit in credits:
            same_account = credit["fields"]["account"] == debit["fields"]["account"]
            if credit["id"] in merged or same_account:
                continue
            shared = (
                debit["reference"] is not None
                and debit["reference"] == credit["reference"]
            )
            near = (
                _days(credit["fields"]["date"], debit["fields"]["date"])
                <= MATCH_WINDOW_DAYS
            )
            same_currency = credit["fields"]["currency"] == debit["fields"]["currency"]
            same_amount = credit["fields"]["amount"] == debit["fields"]["amount"]
            if same_currency and same_amount and (shared or near):
                debit["fields"]["kind"] = "transfer"
                debit["counterpart"] = credit["fields"]["account"]
                debit["keys"] = debit["keys"] + credit["keys"]
                debit["notes"].append(f"paired:{credit['id']}")
                if not shared:
                    debit["notes"].append("pair_inferred")
                credit["status"] = "merged"
                credit["notes"].append(f"merged_into:{debit['id']}")
                merged.add(credit["id"])
                break
            if (
                not same_currency
                and shared
                and credit["id"] not in debit["cross_currency"]
            ):
                debit["cross_currency"].append(credit["id"])
                credit["cross_currency"].append(debit["id"])


def _mark_missing(store: Store, connection: dict, coverage: tuple, seen: set) -> int:
    start, end = coverage
    missing = 0
    for key, observation in store.observations.items():
        txn = observation["txn"]
        if observation["connection"] != connection["id"] or key in seen:
            continue
        if not start <= txn["booked"] <= end:
            continue
        holder = _holder(store, key)
        if txn["pending"]:
            if (
                holder in store.proposals
                and store.proposals[holder]["status"] == "pending"
            ):
                store.proposals[holder]["status"] = "expired"
            continue
        if holder in store.records:
            flag = f"source_no_longer_reports:{key}"
            if flag not in store.records[holder]["flags"]:
                store.records[holder]["flags"].append(flag)
                missing += 1
        elif holder in store.proposals:
            store.proposals[holder]["notes"].append("source_no_longer_reports")
            missing += 1
    return missing


def _matches(store: Store, proposal: dict) -> list[str]:
    fields = proposal["fields"]
    if field_issues({**fields, "kind": "expense"}):
        return []
    sides = [(fields["account"], proposal["direction"])]
    if proposal["counterpart"]:
        sides.append((proposal["counterpart"], "credit"))
    scopes = {_scope(k) for k in proposal["keys"]}
    found = []
    for record in store.records.values():
        if record["owner"] != proposal["owner"]:
            continue
        if scopes & {_scope(k) for k in _record_keys(record)}:
            continue
        other = record["fields"]
        if other["currency"] != fields["currency"] or other["amount"] != fields["amount"]:
            continue
        if _days(other["date"], fields["date"]) > MATCH_WINDOW_DAYS:
            continue
        if any(_record_side(record, account) == side for account, side in sides):
            found.append(record["id"])
    return found


def _refresh_issues(store: Store, proposal: dict) -> None:
    if proposal["status"] == "revision":
        proposal["issues"] = ["source_revised"]
        return
    if proposal["status"] not in ("proposed", "pending"):
        proposal["issues"] = []
        return
    issues = list(field_issues(proposal["fields"]))
    if proposal["status"] == "pending":
        issues.append("pending")
    if any(k.startswith("fp:") for k in proposal["keys"]):
        issues.append("identity_derived")
    if any(n.startswith("reverses:") for n in proposal["notes"]):
        issues.append("reversal_linked")
    if "pair_inferred" in proposal["notes"]:
        issues.append("transfer_pair_inferred")
    for record_id in _matches(store, proposal):
        issues.append(f"possible_match:{record_id}")
    for other in proposal["cross_currency"]:
        issues.append(f"cross_currency_transfer_candidate:{other}")
    proposal["issues"] = [i for i in issues if i not in proposal["acknowledged"]]


def _proposal(store: Store, actor: str, proposal_id: str) -> dict:
    proposal = store.proposals[proposal_id]
    if proposal["owner"] != actor:
        raise PermissionError("only the owner reviews a proposal")
    return proposal


def classify(
    store: Store, actor: str, proposal_id: str, kind: str, counterpart: str | None = None
) -> None:
    proposal = _proposal(store, actor, proposal_id)
    proposal["fields"]["kind"] = kind
    if counterpart:
        proposal["counterpart"] = counterpart
    _refresh_issues(store, proposal)


def unpair(store: Store, actor: str, proposal_id: str) -> None:
    debit = _proposal(store, actor, proposal_id)
    partner_id = next(
        n.split(":", 1)[1] for n in debit["notes"] if n.startswith("paired:")
    )
    credit = store.proposals[partner_id]
    debit["keys"] = [k for k in debit["keys"] if k not in credit["keys"]]
    debit["counterpart"] = None
    debit["fields"]["kind"] = "expense"
    debit["notes"] = [
        n for n in debit["notes"] if n not in (f"paired:{partner_id}", "pair_inferred")
    ]
    debit["notes"].append("pair_rejected")
    credit["status"] = "proposed"
    credit["notes"] = [n for n in credit["notes"] if not n.startswith("merged_into:")]
    credit["notes"].append("pair_rejected")
    _refresh_issues(store, debit)
    _refresh_issues(store, credit)


def acknowledge(store: Store, actor: str, proposal_id: str, issue: str) -> None:
    proposal = _proposal(store, actor, proposal_id)
    proposal["acknowledged"].append(issue)
    _refresh_issues(store, proposal)


def link(store: Store, actor: str, proposal_id: str, record_id: str) -> None:
    proposal = _proposal(store, actor, proposal_id)
    if f"possible_match:{record_id}" not in proposal["issues"]:
        raise ValueError("link only to a surfaced candidate")
    store.records[record_id]["provenance"].append(
        {
            "source": "connection",
            "connection": proposal["connection"],
            "keys": proposal["keys"],
        }
    )
    proposal["status"] = "linked"
    proposal["notes"].append(f"linked:{record_id}")
    store.events.append({"code": "proposal_linked", "connection": proposal["connection"]})
    for other in store.proposals.values():
        _refresh_issues(store, other)


def confirm(store: Store, actor: str, proposal_ids: list[str]) -> dict:
    outcome: dict = {"confirmed": [], "skipped": {}}
    for proposal_id in proposal_ids:
        proposal = _proposal(store, actor, proposal_id)
        _refresh_issues(store, proposal)
        if proposal["status"] != "proposed" or blocking(proposal):
            outcome["skipped"][proposal_id] = blocking(proposal) or [proposal["status"]]
            continue
        store.records[proposal_id] = {
            "id": proposal_id,
            "owner": actor,
            "fields": dict(proposal["fields"]),
            "counterpart": proposal["counterpart"],
            "provenance": [
                {
                    "source": "connection",
                    "connection": proposal["connection"],
                    "keys": list(proposal["keys"]),
                }
            ],
            "user_fields": [],
            "revisions": [],
            "flags": [],
        }
        proposal["status"] = "confirmed"
        outcome["confirmed"].append(proposal_id)
    store.events.append(
        {
            "code": "batch_confirmed",
            "confirmed": len(outcome["confirmed"]),
            "skipped": len(outcome["skipped"]),
        }
    )
    return outcome


def accept_revision(store: Store, actor: str, proposal_id: str) -> None:
    proposal = _proposal(store, actor, proposal_id)
    if proposal["status"] != "revision":
        raise ValueError("not a source revision")
    record = store.records[proposal["record"]]
    before = dict(record["fields"])
    record["fields"].update(proposal["changes"])
    record["revisions"].append(
        {"before": before, "after": dict(record["fields"]), "reason": "source_revised"}
    )
    proposal["status"] = "applied"
    proposal["issues"] = []


def add_manual(
    store: Store, owner: str, fields: dict, counterpart: str | None = None
) -> str:
    if field_issues(fields):
        raise ValueError(f"manual entry incomplete: {field_issues(fields)}")
    record_id = store.new_id("rec")
    store.records[record_id] = {
        "id": record_id,
        "owner": owner,
        "fields": dict(fields),
        "counterpart": counterpart,
        "provenance": [{"source": "manual", "source_id": fields["source_id"]}],
        "user_fields": sorted(FIELDS),
        "revisions": [],
        "flags": [],
    }
    return record_id


def correct(store: Store, actor: str, record_id: str, reason: str, **changes) -> None:
    record = store.records[record_id]
    if record["owner"] != actor or not reason.strip():
        raise ValueError("owner correction with a reason required")
    before = dict(record["fields"])
    record["fields"].update(changes)
    if field_issues(record["fields"]):
        record["fields"] = before
        raise ValueError("correction leaves the record incomplete")
    record["user_fields"] = sorted(set(record["user_fields"]) | set(changes))
    record["revisions"].append(
        {"before": before, "after": dict(record["fields"]), "reason": reason}
    )


def revoke(store: Store, actor: str, connection_id: str) -> dict:
    connection = _owned(store, actor, connection_id)
    if connection["state"] in (CANCELLED, REVOKED):
        raise IllegalTransition(f"{connection['state']} cannot be revoked")
    connection["state"] = REVOKED
    _drop_secret(store, connection)
    withdrawn = 0
    for proposal in store.proposals.values():
        if proposal["connection"] == connection_id and proposal["status"] in OPEN:
            proposal["status"] = "withdrawn"
            proposal["issues"] = []
            withdrawn += 1
    purged = [
        k for k, o in store.observations.items() if o["connection"] == connection_id
    ]
    for key in purged:
        del store.observations[key]
    retained = 0
    for record in store.records.values():
        if any(s.get("connection") == connection_id for s in record["provenance"]):
            record["flags"].append(f"source_revoked:{connection_id}")
            retained += 1
    summary = {
        "withdrawn": withdrawn,
        "observations_purged": len(purged),
        "records_retained": retained,
    }
    store.events.append(
        {"code": "connection_revoked", "connection": connection_id, **summary}
    )
    return summary


def delete_imported(store: Store, actor: str, connection_id: str) -> dict:
    connection = _owned(store, actor, connection_id)
    if connection["state"] != REVOKED:
        raise IllegalTransition("revoke before deleting imported data")
    deleted, kept = [], []
    for record_id, record in list(store.records.items()):
        others = [s for s in record["provenance"] if s.get("connection") != connection_id]
        if len(others) == len(record["provenance"]):
            continue
        if others:
            record["provenance"] = others
            record["flags"] = [f for f in record["flags"] if connection_id not in f]
            kept.append(record_id)
        else:
            del store.records[record_id]
            deleted.append(record_id)
    before = len(store.snapshots)
    store.snapshots = [s for s in store.snapshots if s["connection"] != connection_id]
    summary = {
        "records_deleted": len(deleted),
        "records_kept_other_provenance": len(kept),
        "snapshots_deleted": before - len(store.snapshots),
    }
    store.events.append(
        {"code": "imported_data_deleted", "connection": connection_id, **summary}
    )
    return summary


def freshness(store: Store, account_id: str) -> str | None:
    stamps = [s["as_of"] for s in store.snapshots if s["account"] == account_id]
    return max(stamps) if stamps else None


def reconcile(store: Store, account_id: str, check: dict) -> dict:
    snapshots = [s for s in store.snapshots if s["account"] == account_id]
    latest = max(snapshots, key=lambda s: s["as_of"])
    connection = store.connections[latest["connection"]]
    if check["as_of"] < connection["history_from"]:
        return {
            "status": "history_unavailable",
            "history_from": connection["history_from"],
        }
    activity = Decimal("0")
    for observation in store.observations.values():
        txn = observation["txn"]
        if observation["connection"] != connection["id"] or txn["pending"]:
            continue
        if connection["account_map"].get(txn["account"]) != account_id:
            continue
        if check["as_of"] < txn["booked"] <= latest["as_of"][:10]:
            sign = 1 if txn["direction"] == "credit" else -1
            activity += sign * Decimal(txn["amount"])
    implied = Decimal(latest["amount"]) - activity
    return {
        "status": "compared",
        "check_as_of": check["as_of"],
        "snapshot_as_of": latest["as_of"],
        "implied_at_check": f"{implied:.2f}",
        "difference": f"{Decimal(check['amount']) - implied:.2f}",
    }


def totals(store: Store, owner: str) -> dict:
    result: dict = {}
    for record in store.records.values():
        if record["owner"] != owner:
            continue
        fields = record["fields"]
        group = result.setdefault(fields["currency"], {}).setdefault(
            fields["destination"],
            {"expense": Decimal("0"), "income": Decimal("0"), "transfer": Decimal("0")},
        )
        kind = "expense" if fields["kind"] == "refund" else fields["kind"]
        sign = -1 if fields["kind"] == "refund" else 1
        group[kind] += sign * Decimal(fields["amount"])
    return {
        currency: {
            destination: {kind: f"{amount:.2f}" for kind, amount in group.items()}
            for destination, group in destinations.items()
        }
        for currency, destinations in result.items()
    }


def kit_oracle_totals(store: Store, owner: str) -> dict:
    rows = [
        {**record["fields"], "source_id": record["id"]}
        for record in store.records.values()
        if record["owner"] == owner
    ]
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "confirmed-records.json"
        source.write_text(json.dumps({"rows": rows}))
        kit = Harness(Path(folder) / "state.json")
        ingested = kit.ingest(source)
        outcome = kit.confirm(ingested["ids"])
        if outcome["skipped"]:
            raise AssertionError(f"kit rejected connector records: {outcome['skipped']}")
        return kit.totals()


class Checks:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, case: str, claim: str, passed: bool, **observed) -> None:
        self.items.append(
            {"case": case, "claim": claim, "passed": bool(passed), "observed": observed}
        )


def _open_ids(store: Store, connection_id: str) -> list[str]:
    return [
        p["id"]
        for p in store.proposals.values()
        if p["connection"] == connection_id and p["status"] == "proposed"
    ]


def _by_key(store: Store, suffix: str) -> dict:
    return next(
        p
        for p in store.proposals.values()
        if p["status"] not in ("merged", "revision")
        and any(k.endswith(suffix) for k in p["keys"])
    )


CHK, SAV, CARD, BIZ = "src-chk-dop", "src-sav-usd", "src-card-dop", "src-biz-dop"


def tx(
    account: str,
    booked: str,
    amount: str,
    direction: str,
    description: str,
    institution_id: str | None = None,
    currency: str = "DOP",
    **extra,
) -> Txn:
    return Txn(
        account, booked, amount, direction, currency, description, institution_id, **extra
    )


def scenario(checks: Checks) -> dict:
    corpus = build_corpus(71)
    merchant = corpus["merchant"]
    store = Store()
    owner, partner = "user-a", "user-b"
    store.accounts["acct-cash-dop"] = {
        "owner": owner,
        "name": "Efectivo",
        "currency": "DOP",
    }
    store.accounts["acct-chk-dop"] = {
        "owner": owner,
        "name": "Cuenta corriente (manual)",
        "currency": "DOP",
    }
    manual_ids = {}
    for row in corpus["manual"]:
        fields = {**row, "account": "acct-cash-dop"}
        counterpart = "acct-chk-dop" if row["kind"] == "transfer" else None
        manual_ids[row["source_id"]] = add_manual(store, owner, fields, counterpart)
    store.balance_checks += [
        {
            "account": "acct-chk-dop",
            "as_of": "2026-09-05",
            "amount": "1500.00",
            "currency": "DOP",
        },
        {
            "account": "acct-chk-dop",
            "as_of": "2026-08-20",
            "amount": "1420.00",
            "currency": "DOP",
        },
    ]
    timeline = []

    def mark(step: str, connection_id: str) -> None:
        connection = store.connections[connection_id]
        timeline.append(
            {
                "step": step,
                "connection": connection_id,
                "state": connection["state"],
                "last_success_at": connection["last_success_at"],
                "records": len(store.records),
            }
        )

    abandoned = connect(
        store,
        owner,
        "aggregator_api",
        {"src-chk-dop": "acct-chk-dop", "src-sav-usd": None},
        secret=SECRET,
    )
    authenticate(store, owner, abandoned, "mfa_challenge")
    mark("first attempt asks for MFA", abandoned)
    authenticate(store, owner, abandoned, "cancelled")
    mark("person cancels MFA", abandoned)
    try:
        refresh(store, owner, abandoned, Refresh(at="2026-09-15T09:01"))
        refused = False
    except IllegalTransition:
        refused = True
    checks.add(
        "mfa_cancelled",
        "A cancelled MFA challenge leaves no secret, no data and no refresh path",
        refused
        and store.connections[abandoned]["vault_handle"] is None
        and SECRET not in store.vault.values()
        and not any(o["connection"] == abandoned for o in store.observations.values()),
        state=store.connections[abandoned]["state"],
        refresh_refused=refused,
    )

    twins = [
        r for r in corpus["transactions"] if r["source_id"] in ("tx-dop-02", "tx-dop-03")
    ]
    card_csv = connect(store, owner, "file_import", {"csv-card": None})
    authenticate(store, owner, card_csv, "authenticated")
    csv_rows = tuple(
        tx(
            "csv-card",
            r["date"],
            r["amount"],
            "debit",
            r["description"],
            None,
            r["currency"],
        )
        for r in twins
    ) + (tx("csv-card", "2026-09-11", "45.00", "debit", "FARMACIA"),)
    csv_account = (SourceAccount("csv-card", "Tarjeta (archivo)", "DOP"),)
    first_csv = refresh(
        store,
        owner,
        card_csv,
        Refresh(
            at="2026-09-12T20:00",
            accounts=csv_account,
            txns=csv_rows,
            coverage=("2026-09-01", "2026-09-11"),
        ),
    )
    confirm(store, owner, _open_ids(store, card_csv))
    card_account = store.connections[card_csv]["account_map"]["csv-card"]
    again = refresh(
        store,
        owner,
        card_csv,
        Refresh(
            at="2026-09-12T20:05",
            accounts=csv_account,
            txns=csv_rows,
            coverage=("2026-09-01", "2026-09-11"),
        ),
    )
    overlap = refresh(
        store,
        owner,
        card_csv,
        Refresh(
            at="2026-09-14T19:00",
            accounts=csv_account,
            txns=csv_rows
            + (tx("csv-card", "2026-09-13", "60.00", "debit", "PANADERIA"),),
            coverage=("2026-09-05", "2026-09-13"),
        ),
    )
    confirm(store, owner, _open_ids(store, card_csv))
    twin_records = [
        r["id"]
        for r in store.records.values()
        if r["fields"]["account"] == card_account
        and r["fields"]["description"] == merchant
    ]
    checks.add(
        "repeated_import",
        "Re-importing the same export adds nothing; an overlapping export adds only its new row",
        first_csv["new_proposals"] == 3
        and again["new_proposals"] == 0
        and again["seen"] == 3
        and overlap["new_proposals"] == 1
        and overlap["seen"] == 3,
        first=first_csv["new_proposals"],
        repeat=again["new_proposals"],
        overlapping_new=overlap["new_proposals"],
    )
    checks.add(
        "missing_institution_ids",
        "Rows without institution ids get derived identities; same-day twins stay two records",
        len(twin_records) == 2
        and all(
            k.startswith("fp:")
            for r in twin_records
            for k in _record_keys(store.records[r])
        ),
        twin_records=len(twin_records),
    )

    bank = connect(
        store,
        owner,
        "aggregator_api",
        {
            "src-chk-dop": "acct-chk-dop",
            "src-sav-usd": None,
            "src-card-dop": card_account,
        },
        secret=SECRET,
    )
    authenticate(store, owner, bank, "mfa_challenge")
    authenticate(store, owner, bank, "authenticated")
    mark("second attempt passes MFA", bank)
    statement = {r["source_id"]: r for r in corpus["statement"]}
    usd = next(r for r in corpus["transactions"] if r["source_id"] == "tx-usd-01")
    direction = {"income": "credit", "refund": "credit", "expense": "debit"}
    checking = tuple(
        tx(
            CHK,
            r["date"],
            r["amount"],
            direction[r["kind"]],
            r["description"],
            f"T-000{i}",
            r["currency"],
        )
        for i, r in enumerate(statement.values(), 1)
    ) + (
        tx(CHK, "2026-09-11", "300.00", "credit", "DEPOSITO EFECTIVO", "T-0005"),
        tx(
            CHK,
            "2026-09-12",
            "200.00",
            "debit",
            "PAGO TARJETA",
            "T-0006",
            reference="REF-551",
        ),
        tx(CHK, "2026-09-14", "95.00", "debit", "FERRETERIA FICTICIA", "T-0008"),
        tx(
            CHK,
            "2026-09-13",
            "590.00",
            "debit",
            "TRANSFERENCIA A CUENTA USD",
            "T-0007",
            reference="REF-778",
        ),
    )
    savings = (
        tx(
            SAV,
            "2026-09-13",
            "10.00",
            "credit",
            "TRANSFERENCIA RECIBIDA",
            "S-0201",
            "USD",
            reference="REF-778",
        ),
        tx(
            SAV,
            usd["date"],
            usd["amount"],
            "debit",
            usd["description"],
            "S-0202",
            usd["currency"],
        ),
    )
    card = (
        tx(CARD, twins[0]["date"], twins[0]["amount"], "debit", merchant, "C-0101"),
        tx(CARD, twins[1]["date"], twins[1]["amount"], "debit", merchant, "C-0102"),
        tx(CARD, "2026-09-11", "45.00", "debit", "FARMACIA FICTICIA", "C-0103"),
        tx(CARD, "2026-09-12", "80.00", "debit", "TIENDA FICTICIA", "C-0104"),
        tx(
            CARD,
            "2026-09-12",
            "200.00",
            "credit",
            "PAGO RECIBIDO",
            "C-0105",
            reference="REF-551",
        ),
        tx(CARD, "2026-09-13", "95.00", "credit", "DEVOLUCION FICTICIA", "C-0110"),
        tx(CARD, "2026-09-13", "60.00", "debit", "PANADERIA", "C-0106"),
        tx(CARD, "2026-09-14", "60.00", "debit", "RESTAURANTE", "P-0107", pending=True),
    )
    business = (tx(BIZ, "2026-09-12", "500.00", "debit", "PROVEEDOR", "B-0001"),)
    accounts = (
        SourceAccount("src-chk-dop", "Cuenta Corriente", "DOP"),
        SourceAccount("src-sav-usd", "Ahorro Dolares", "USD"),
        SourceAccount("src-card-dop", "Tarjeta Clasica", "DOP"),
        SourceAccount("src-biz-dop", "Cuenta Empresa", "DOP"),
    )

    def balances(at: str, card_owed: str) -> tuple[Balance, ...]:
        return (
            Balance("src-chk-dop", at, "1879.50", "DOP"),
            Balance("src-sav-usd", at, "1250.00", "USD"),
            Balance("src-card-dop", at, card_owed, "DOP"),
            Balance("src-biz-dop", at, "999.00", "DOP"),
        )

    first = refresh(
        store,
        owner,
        bank,
        Refresh(
            at="2026-09-15T09:06",
            accounts=accounts,
            balances=balances("2026-09-15T06:00", "1030.50"),
            txns=checking + savings + card + business,
            coverage=("2026-09-01", "2026-09-15"),
        ),
    )
    mark("first refresh", bank)
    mapping = store.connections[bank]["account_map"]
    checks.add(
        "initial_connection_and_selection",
        "Only selected source accounts map to Argus accounts; the unselected account stores nothing",
        set(mapping) == {"src-chk-dop", "src-sav-usd", "src-card-dop"}
        and mapping["src-chk-dop"] == "acct-chk-dop"
        and mapping["src-card-dop"] == card_account
        and first["discarded_unconsented"] == 1
        and not any("src-biz-dop" in k for k in store.observations)
        and all(s["account"] in mapping.values() for s in store.snapshots),
        mapped=len(mapping),
        discarded=first["discarded_unconsented"],
    )
    records_before = len(store.records)
    reconciled = reconcile(store, "acct-chk-dop", store.balance_checks[0])
    too_old = reconcile(store, "acct-chk-dop", store.balance_checks[1])
    records_after_reconcile = len(store.records)

    deposit = _by_key(store, ":T-0005")
    manual_transfer = manual_ids["manual-transfer"]
    link(store, owner, deposit["id"], manual_transfer)
    classify(store, owner, _by_key(store, ":T-0001")["id"], "income")
    classify(store, owner, _by_key(store, ":T-0004")["id"], "refund")
    outbound = _by_key(store, ":T-0007")
    inbound = _by_key(store, ":S-0201")
    cross_flagged = any(
        i.startswith("cross_currency") for i in outbound["issues"]
    ) and any(i.startswith("cross_currency") for i in inbound["issues"])
    for proposal, other_account in (
        (outbound, inbound["fields"]["account"]),
        (inbound, None),
    ):
        for issue in [i for i in proposal["issues"] if i.startswith("cross_currency")]:
            acknowledge(store, owner, proposal["id"], issue)
        classify(store, owner, proposal["id"], "transfer", other_account)
    guessed = _by_key(store, ":T-0008")
    guessed_issues = list(guessed["issues"])
    unpair(store, owner, guessed["id"])
    refund = _by_key(store, ":C-0110")
    classify(store, owner, refund["id"], "refund")
    migrated = {}
    for suffix in (":C-0101", ":C-0102", ":C-0103", ":C-0106"):
        proposal = _by_key(store, suffix)
        candidates = [
            i.split(":", 1)[1]
            for i in proposal["issues"]
            if i.startswith("possible_match:")
        ]
        migrated[suffix] = candidates
        link(store, owner, proposal["id"], candidates[0])
    pending = _by_key(store, ":P-0107")
    pending_refused = confirm(store, owner, [pending["id"]])
    confirm(store, owner, _open_ids(store, bank))
    mark("person reviews first refresh", bank)

    checks.add(
        "manual_cash_overlap",
        "A bank deposit that matches a manual cash-to-account transfer links to it instead of adding income",
        deposit["status"] == "linked"
        and len(store.records[manual_transfer]["provenance"]) == 2
        and not any(
            r["fields"]["source_id"].endswith(":T-0005") for r in store.records.values()
        ),
        linked_to=manual_transfer,
    )
    checks.add(
        "balance_check_overlap",
        "A recorded balance check is compared with imported activity; the gap is reported, never invented",
        reconciled["status"] == "compared"
        and reconciled["difference"] == "10.00"
        and too_old["status"] == "history_unavailable"
        and records_before == records_after_reconcile,
        compared=reconciled,
        before_history=too_old,
    )
    transfer = _by_key(store, ":T-0006")
    checks.add(
        "own_account_transfers",
        "Bank-referenced sides pair into one transfer; an unreferenced look-alike pair waits for the person; DOP to USD is flagged, never converted",
        transfer["status"] == "confirmed"
        and transfer["fields"]["kind"] == "transfer"
        and len(transfer["keys"]) == 2
        and "transfer_pair_inferred" in guessed_issues
        and store.records[guessed["id"]]["fields"]["kind"] == "expense"
        and store.records[refund["id"]]["fields"]["kind"] == "refund"
        and cross_flagged
        and store.records[outbound["id"]]["fields"]["currency"] == "DOP"
        and store.records[inbound["id"]]["fields"]["currency"] == "USD",
        pair_keys=len(transfer["keys"]),
        inferred_pair_issues=guessed_issues,
        cross_currency_flagged=cross_flagged,
    )
    card_records = [
        r for r in store.records.values() if r["fields"]["account"] == card_account
    ]
    both_methods = [r for r in card_records if len(r["provenance"]) == 2]
    checks.add(
        "retrieval_method_migration",
        "API observations link to records first imported from a CSV file; ambiguous twins are surfaced, and no duplicate appears",
        [len(migrated[k]) for k in (":C-0101", ":C-0102", ":C-0103", ":C-0106")]
        == [2, 1, 1, 1]
        and len(both_methods) == 4
        and len(card_records) == 6,
        candidates_per_row={k.lstrip(":"): len(v) for k, v in migrated.items()},
        card_records=len(card_records),
        records_with_both_methods=len(both_methods),
    )

    farmacia_id = next(
        r["id"]
        for r in store.records.values()
        if r["fields"]["description"] == "FARMACIA"
    )
    correct(
        store, owner, farmacia_id, "user renamed the purchase", description="Medicinas"
    )
    try:
        refresh(store, partner, bank, Refresh(at="2026-09-16T05:00"))
        partner_refused = False
    except PermissionError:
        partner_refused = True

    revised_card = tuple(
        replace(t, amount="54.00") if t.institution_id == "C-0103" else t
        for t in card
        if not t.pending
    ) + (
        tx(
            CARD,
            "2026-09-15",
            "66.00",
            "debit",
            "RESTAURANTE",
            "C-0107",
            pending_ref="P-0107",
        ),
        tx(
            CARD,
            "2026-09-15",
            "80.00",
            "credit",
            "REVERSO TIENDA FICTICIA",
            "C-0108",
            reverses_ref="C-0104",
        ),
        tx(
            CARD,
            "2026-09-15",
            "30.00",
            "debit",
            "ESTACIONAMIENTO",
            "P-0109",
            pending=True,
        ),
    )
    renamed = (SourceAccount("src-chk-dop", "Cuenta Nomina Plus", "DOP"),) + accounts[1:]
    second_rows = (
        tuple(t for t in checking if t.institution_id != "T-0003")
        + savings
        + revised_card
        + business
    )
    second = refresh(
        store,
        owner,
        bank,
        Refresh(
            at="2026-09-16T06:10",
            accounts=renamed,
            balances=balances("2026-09-16T06:00", "1216.50"),
            txns=second_rows,
            coverage=("2026-09-01", "2026-09-16"),
        ),
    )
    mark("second refresh", bank)
    revision = next(p for p in store.proposals.values() if p["status"] == "revision")
    accept_revision(store, owner, revision["id"])
    confirm(store, owner, _open_ids(store, bank))
    posted = _by_key(store, ":C-0107")
    reversal = _by_key(store, ":C-0108")
    original = _by_key(store, ":C-0104")
    vanished = _by_key(store, ":T-0003")
    checks.add(
        "pending_to_posted",
        "A pending hold is never confirmable; its posted replacement supersedes it with the final amount",
        pending_refused["skipped"].get(pending["id"]) == ["pending"]
        and store.proposals[pending["id"]]["status"] == "superseded"
        and posted["status"] == "confirmed"
        and store.records[posted["id"]]["fields"]["amount"] == "66.00"
        and not any(
            r["fields"]["amount"] == "60.00"
            and "RESTAURANTE" in r["fields"]["description"]
            for r in store.records.values()
        ),
        pending_status=store.proposals[pending["id"]]["status"],
    )
    farmacia = store.records[farmacia_id]
    checks.add(
        "source_revision",
        "A source amount revision becomes a reviewable change that keeps the person's own edits",
        second["revisions"] == 1
        and farmacia["fields"]["amount"] == "54.00"
        and farmacia["fields"]["description"] == "Medicinas"
        and [r["reason"] for r in farmacia["revisions"]]
        == ["user renamed the purchase", "source_revised"],
        revision_reasons=[r["reason"] for r in farmacia["revisions"]],
    )
    checks.add(
        "reversal",
        "A reversal links to the original purchase and nets it to zero instead of deleting it",
        reversal["status"] == "confirmed"
        and store.records[reversal["id"]]["fields"]["kind"] == "refund"
        and f"reverses:{original['id']}" in reversal["notes"]
        and original["id"] in store.records,
        reverses=original["id"],
    )
    checks.add(
        "source_stops_reporting",
        "A posted row the source stops reporting stays recorded and is flagged for review",
        vanished["id"] in store.records
        and any(
            f.startswith("source_no_longer_reports")
            for f in store.records[vanished["id"]]["flags"]
        ),
        flags=store.records[vanished["id"]]["flags"],
    )
    connection = store.connections[bank]
    checks.add(
        "account_rename",
        "A renamed source account keeps its identity, Argus account and records",
        connection["names"]["src-chk-dop"] == "Cuenta Nomina Plus"
        and connection["account_map"]["src-chk-dop"] == "acct-chk-dop"
        and store.accounts["acct-chk-dop"]["name"] == "Cuenta corriente (manual)"
        and second["new_source_accounts"] == 0,
        source_name=connection["names"]["src-chk-dop"],
    )
    oracle = kit_oracle_totals(store, owner)
    mine = totals(store, owner)
    checks.add(
        "kit_contract_and_totals",
        "Every confirmed connector record passes the kit field contract and reproduces the kit's totals",
        oracle == mine,
        connector_totals=mine,
        kit_totals=oracle,
    )
    checks.add(
        "currencies_stay_separate",
        "DOP and USD totals never combine and no conversion is applied",
        set(mine) == {"DOP", "USD"}
        and mine["USD"]["personal"]
        == {"expense": "40.00", "income": "0.00", "transfer": "10.00"},
        usd=mine["USD"],
    )

    records_after_second = len(store.records)
    last_good = connection["last_success_at"]
    fresh_before = freshness(store, "acct-chk-dop")
    expired = refresh(
        store, owner, bank, Refresh(at="2026-09-17T06:00", failure="session_expired")
    )
    mark("session expires", bank)
    authenticate(store, owner, bank, "cancelled")
    still_waiting = store.connections[bank]["state"]
    authenticate(store, owner, bank, "authenticated")
    mark("person reconnects", bank)
    down = refresh(
        store, owner, bank, Refresh(at="2026-09-18T06:00", failure="source_failed")
    )
    mark("source unavailable", bank)
    malformed_row = next(
        r for r in corpus["transactions"] if r["source_id"] == "tx-number"
    )
    late_row = tx(CHK, "2026-09-18", "15.00", "debit", "PEAJE", "T-0010")
    malformed = tx(
        CHK,
        "2026-09-18",
        malformed_row["amount"],
        "debit",
        malformed_row["description"],
        "T-0011",
    )
    broken_rows = second_rows + (late_row, malformed)
    observations_before = len(store.observations)
    rejected = refresh(
        store,
        owner,
        bank,
        Refresh(
            at="2026-09-19T06:00",
            accounts=renamed,
            balances=balances("2026-09-19T06:00", "1216.50"),
            txns=broken_rows,
            coverage=("2026-09-01", "2026-09-19"),
        ),
    )
    mark("malformed batch rejected", bank)
    checks.add(
        "expired_session",
        "An expired session asks for reconnection; records and last success stay as they were",
        expired["state"] == REAUTH_REQUIRED
        and still_waiting == REAUTH_REQUIRED
        and len(store.records) == records_after_second,
        state_after_cancel=still_waiting,
    )
    checks.add(
        "source_failure_keeps_last_good",
        "Failed refreshes keep records, last success time and balance freshness; a malformed batch applies nothing",
        down["state"] == DEGRADED
        and rejected["applied"] is False
        and store.connections[bank]["last_success_at"] == last_good
        and freshness(store, "acct-chk-dop") == fresh_before
        and len(store.observations) == observations_before
        and len(store.records) == records_after_second,
        last_success_at=store.connections[bank]["last_success_at"],
        balance_as_of=freshness(store, "acct-chk-dop"),
    )
    checks.add(
        "partial_history_and_stale_balance",
        "Coverage shorter than requested is recorded, and a stale balance keeps its old as-of time",
        store.connections[bank]["history_from"] == "2026-09-01"
        and fresh_before == "2026-09-16T06:00"
        and freshness(store, "acct-chk-dop") == "2026-09-16T06:00",
        history_from=store.connections[bank]["history_from"],
        balance_as_of=freshness(store, "acct-chk-dop"),
    )

    reissued = renamed + (SourceAccount("src-card-dop-2", "Tarjeta Clasica", "DOP"),)
    recovered = refresh(
        store,
        owner,
        bank,
        Refresh(
            at="2026-09-20T06:00",
            accounts=reissued,
            balances=balances("2026-09-20T06:00", "1231.50"),
            txns=tuple(t for t in second_rows if t.institution_id != "P-0109")
            + (
                late_row,
                tx(
                    "src-card-dop-2",
                    "2026-09-19",
                    "25.00",
                    "debit",
                    "CAFETERIA",
                    "N-0001",
                ),
            ),
            coverage=("2026-09-01", "2026-09-20"),
        ),
    )
    mark("source recovers", bank)
    checks.add(
        "idempotent_refresh",
        "A recovered refresh re-sees every known row and proposes only the genuinely new one",
        recovered["new_proposals"] == 1
        and recovered["seen"]
        == len(
            [
                t
                for t in second_rows
                if t.account in mapping and t.institution_id != "P-0109"
            ]
        )
        and _by_key(store, ":P-0109")["status"] == "expired",
        seen=recovered["seen"],
        new=recovered["new_proposals"],
    )
    checks.add(
        "reissued_card",
        "A new source account after consent becomes an owner decision, not a silent new account",
        recovered["new_source_accounts"] == 1
        and recovered["discarded_unconsented"] == 2
        and "src-card-dop-2" not in store.connections[bank]["account_map"],
        link_requests=len(store.account_links),
    )

    confirm(store, owner, _open_ids(store, bank))
    revoked = revoke(store, owner, bank)
    mark("person disconnects", bank)
    try:
        refresh(store, owner, bank, Refresh(at="2026-09-21T06:00"))
        refused_after_revoke = False
    except IllegalTransition:
        refused_after_revoke = True
    deleted = delete_imported(store, owner, bank)
    mark("person deletes imported data", bank)
    survivors = store.records
    checks.add(
        "revocation_and_deletion",
        "Revoking destroys the secret and stops refresh; deletion removes connection-only records and keeps shared or manual ones",
        refused_after_revoke
        and SECRET not in store.vault.values()
        and not any(o["connection"] == bank for o in store.observations.values())
        and manual_transfer in survivors
        and all(r in survivors for r in manual_ids.values())
        and len([r for r in survivors.values() if r["fields"]["account"] == card_account])
        == 4
        and deleted["records_deleted"] > 0
        and not any(s["connection"] == bank for s in store.snapshots)
        and len(store.balance_checks) == 2,
        revoke=revoked,
        delete=deleted,
    )

    public = json.dumps(
        {"events": store.events, "state": store.without_vault(), "timeline": timeline},
        default=str,
    )
    event_text = json.dumps(store.events)
    sensitive = (
        {t.amount for t in second_rows}
        | {t.description for t in second_rows}
        | {merchant}
    )
    checks.add(
        "privacy_boundaries",
        "Events carry codes and counts only; the secret never leaves the vault; a partner cannot refresh",
        not any(value in event_text for value in sensitive)
        and SECRET not in public
        and partner_refused,
        events=len(store.events),
    )
    return {"timeline": timeline, "reconciliation": [reconciled, too_old]}


def routine_feed(seed: int = 71, days: int = 60) -> list[tuple[int, Txn]]:
    rng = random.Random(seed)
    fake = Faker("es_ES")
    fake.seed_instance(seed)
    merchants = [f"Comercio Ficticio {fake.last_name()}" for _ in range(10)]
    start = date(2026, 7, 1)
    rows: list[tuple[int, Txn]] = []
    counter = 0

    def next_id(prefix: str) -> str:
        nonlocal counter
        counter += 1
        return f"{prefix}-{counter:05d}"

    for offset in range(days):
        day = start + timedelta(days=offset)
        booked = day.isoformat()
        if day.day in (15, 30):
            rows.append(
                (
                    offset,
                    tx(
                        "chk",
                        booked,
                        "35000.00",
                        "credit",
                        "NOMINA FICTICIA",
                        next_id("T"),
                    ),
                )
            )
        if day.day == 20:
            reference = f"REF-{offset:03d}"
            rows.append(
                (
                    offset,
                    tx(
                        "chk",
                        booked,
                        "12000.00",
                        "debit",
                        "PAGO TARJETA",
                        next_id("T"),
                        reference=reference,
                    ),
                )
            )
            rows.append(
                (
                    offset,
                    tx(
                        "card",
                        booked,
                        "12000.00",
                        "credit",
                        "PAGO RECIBIDO",
                        next_id("C"),
                        reference=reference,
                    ),
                )
            )
        for _ in range(rng.choice((0, 1, 1, 2))):
            amount = f"{Decimal(rng.randrange(1500, 450000)) / 100:.2f}"
            merchant = rng.choice(merchants)
            posted_id = next_id("C")
            if rng.random() < 0.2:
                hold = next_id("P")
                later = (day + timedelta(days=1)).isoformat()
                rows.append(
                    (
                        offset,
                        tx("card", booked, amount, "debit", merchant, hold, pending=True),
                    )
                )
                rows.append(
                    (
                        offset + 1,
                        tx(
                            "card",
                            later,
                            amount,
                            "debit",
                            merchant,
                            posted_id,
                            pending_ref=hold,
                        ),
                    )
                )
            else:
                rows.append(
                    (offset, tx("card", booked, amount, "debit", merchant, posted_id))
                )
        if rng.random() < 0.3:
            amount = f"{Decimal(rng.randrange(1500, 250000)) / 100:.2f}"
            rows.append(
                (
                    offset,
                    tx(
                        "chk",
                        booked,
                        amount,
                        "debit",
                        rng.choice(merchants),
                        next_id("T"),
                    ),
                )
            )
    return rows


def _window(rows: list[tuple[int, Txn]], day: int, span: int = 30) -> tuple[Txn, ...]:
    visible = []
    posted_refs = {t.pending_ref for d, t in rows if d <= day and t.pending_ref}
    for available, txn in rows:
        if available > day or available < day - span:
            continue
        if txn.pending and txn.institution_id in posted_refs:
            continue
        visible.append(txn)
    return tuple(visible)


def workload(refresh_every: int, review_every: int, days: int = 60) -> dict:
    rows = routine_feed(days=days)
    store = Store()
    owner = "user-w"
    connection = connect(
        store, owner, "bank_api", {"chk": None, "card": None}, secret=SECRET
    )
    authenticate(store, owner, connection, "authenticated")
    accounts = (
        SourceAccount("chk", "Corriente", "DOP"),
        SourceAccount("card", "Tarjeta", "DOP"),
    )
    stats = {
        "refreshes": 0,
        "rows_reseen": 0,
        "new_rows": 0,
        "per_row_actions": 0,
        "batch_actions": 0,
        "exception_actions": 0,
    }
    for day in range(days):
        if (day + 1) % refresh_every == 0 or day == days - 1:
            start = (date(2026, 7, 1) + timedelta(days=max(0, day - 30))).isoformat()
            end = (date(2026, 7, 1) + timedelta(days=day)).isoformat()
            outcome = refresh(
                store,
                owner,
                connection,
                Refresh(
                    at=f"{end}T23:00",
                    accounts=accounts,
                    txns=_window(rows, day),
                    coverage=(start, end),
                ),
            )
            stats["refreshes"] += 1
            stats["rows_reseen"] += outcome["seen"]
            stats["new_rows"] += outcome["new_proposals"]
        if (day + 1) % review_every == 0 or day == days - 1:
            waiting = [store.proposals[p] for p in _open_ids(store, connection)]
            clean = [p["id"] for p in waiting if not blocking(p)]
            exceptions = [p for p in waiting if blocking(p)]
            if clean:
                stats["batch_actions"] += 1
                stats["per_row_actions"] += len(clean)
                confirm(store, owner, clean)
            for proposal in exceptions:
                if blocking(proposal) != ["kind"] or proposal["direction"] != "credit":
                    raise AssertionError(
                        f"unplanned routine exception: {blocking(proposal)}"
                    )
                classify(store, owner, proposal["id"], "income")
                if confirm(store, owner, [proposal["id"]])["skipped"]:
                    raise AssertionError("classified credit still blocked")
                stats["exception_actions"] += 1
                stats["per_row_actions"] += 1
    superseded = sum(1 for p in store.proposals.values() if p["status"] == "superseded")
    return {
        "refresh_every_days": refresh_every,
        "review_every_days": review_every,
        **stats,
        "pending_superseded_without_review": superseded,
        "actions_if_every_row_is_confirmed_alone": stats["per_row_actions"],
        "actions_with_batch_review": stats["batch_actions"] + stats["exception_actions"],
        "actions_if_clean_rows_were_auto_accepted": stats["exception_actions"],
        "records": len(store.records),
    }


def naive_kit_reuse(days: int = 60, every: int = 7) -> list[dict]:
    rows = routine_feed(days=days)
    results = []
    kind = {"credit": "income", "debit": "expense"}
    with tempfile.TemporaryDirectory() as folder:
        kit = Harness(Path(folder) / "state.json")
        for day in range(every - 1, days, every):
            export = Path(folder) / f"export-day-{day:02d}.csv"
            posted = [t for t in _window(rows, day) if not t.pending]
            with export.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                for txn in posted:
                    writer.writerow(
                        {
                            "source_id": txn.institution_id,
                            "date": txn.booked,
                            "description": txn.description,
                            "amount": txn.amount,
                            "currency": txn.currency,
                            "kind": kind[txn.direction],
                            "account": txn.account,
                            "destination": "personal",
                        }
                    )
            ingested = kit.ingest(export)
            fresh = [kit.proposals[i] for i in ingested["ids"]]
            flagged = [p for p in fresh if "possible_overlap" in p["issues"]]
            kit.confirm([p["id"] for p in fresh if not p["issues"]])
            results.append(
                {
                    "export_day": day + 1,
                    "rows_in_export": len(posted),
                    "flagged_possible_overlap": len(flagged),
                }
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the synthetic bank-connection lifecycle experiment."
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    checks = Checks()
    story = scenario(checks)
    report = {
        "format": "dominican-bank-connectivity-lifecycle-v1",
        "fictional": True,
        "checks": checks.items,
        "passed": sum(c["passed"] for c in checks.items),
        "failed": [c["case"] for c in checks.items if not c["passed"]],
        "timeline": story["timeline"],
        "review_workload": [workload(1, 1), workload(1, 7), workload(7, 7)],
        "naive_file_identity_reuse": naive_kit_reuse(),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        f"{report['passed']}/{len(checks.items)} checks passed; report at {args.report}"
    )
    for case in report["failed"]:
        print(f"FAILED: {case}")
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
