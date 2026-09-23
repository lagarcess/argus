"""Confirmed finance commands over audited synchronous canonical domain writers."""

from __future__ import annotations

import hashlib
import inspect
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Callable

from pydantic import BaseModel, Field, ValidationError, create_model

from ..store import Store
from . import credit, investing, ledger, planning, tax_estate
from .command_contracts import (
    CommandCurrency,
    CommandDeclaration,
    CommandExecution,
    CommandField,
    CommandReceipt,
    CommandTarget,
    Proposal,
)
from .common import (
    Evidence,
    Model,
    PlatformError,
    assert_active_context,
    identifier,
    minor_units,
    now,
)
from .identity import Identity
from .identity_contracts import MemoryWrite
from .ledger_contracts import (
    AccountCreate,
    AccountPatch,
    TransactionCreate,
    TransactionPatch,
)
from .planning_contracts import (
    AllocationInput,
    BillInput,
    BudgetInput,
    GoalInput,
    PayInput,
    ScenarioInput,
)
from .service_contracts import (
    Beneficiaries,
    Checklist,
    Contact,
    CreditAccount,
    Document,
    EstateAsset,
    Organizer,
    TaxItem,
    TaxScenario,
    record,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS p_command_proposals (
 id TEXT PRIMARY KEY, household_id TEXT NOT NULL, user_id TEXT NOT NULL,
 conversation_id TEXT NOT NULL, request_id TEXT NOT NULL, request_hash TEXT NOT NULL,
 command_name TEXT NOT NULL, revision INTEGER NOT NULL, data_generation INTEGER NOT NULL,
 role TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','superseded','consumed','cancelled')),
 document TEXT NOT NULL, dependencies TEXT NOT NULL,
 UNIQUE(household_id,conversation_id,request_id), UNIQUE(household_id,conversation_id,revision)
);
CREATE INDEX IF NOT EXISTS p_command_proposals_current ON p_command_proposals(household_id,conversation_id,status);
CREATE TABLE IF NOT EXISTS p_command_receipts (
 id TEXT PRIMARY KEY, household_id TEXT NOT NULL, proposal_id TEXT NOT NULL UNIQUE REFERENCES p_command_proposals(id),
 document TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS p_command_receipts_immutable BEFORE UPDATE ON p_command_receipts
 BEGIN SELECT RAISE(ABORT,'immutable_command_receipt'); END;
"""
PROPOSAL_TTL = timedelta(minutes=15)
MAX_ARGUMENT_BYTES = 32768


def _public_model(name, model, *, partial=False):
    fields = {}
    for key, field in model.model_fields.items():
        if key == "idempotency_key":
            continue
        if partial:
            fields[key] = (field.annotation | None, None)
        else:
            fields[key] = (field.annotation, deepcopy(field))
    return create_model(name, __base__=Model, **fields)


@dataclass(frozen=True)
class CommandSpec:
    name: str
    model: type[BaseModel]
    page: str
    handler: Callable
    reference: str | None = None
    edit: bool = False
    currency_path: str | None = None
    account_field: str | None = None
    operation: str = "create"
    parent: tuple[str, str] | None = None
    execution: CommandExecution = CommandExecution()
    review_fields: tuple[str, ...] = ()
    reference_page: str | None = None

    @property
    def input_model(self):
        public = _public_model(
            self.name.replace(".", "_") + "Values", self.model, partial=self.edit
        )
        if self.reference:
            return create_model(
                self.name.replace(".", "_") + "Command",
                __base__=Model,
                record_id=(str, Field(min_length=1, max_length=160)),
                **{("changes" if self.edit else "values"): (public, ...)},
            )
        return public


def _memory_create(store, context, payload, record_id):
    from .settings import create_memory

    return create_memory(payload, context, Identity(store))


def _memory_edit(store, context, payload, record_id):
    from .settings import update_memory

    return update_memory(record_id, payload, context, Identity(store))


def _record_bill_payment(store, context, payload, record_id):
    occurrence = planning.record_occurrence(
        store, context, record_id, payload.due_date, True
    )
    # The bill owner creates the canonical ledger transaction atomically.
    return _read(store, context, "transaction", occurrence["transaction_id"])


# Each handler below calls one existing synchronous domain owner. None initialize
# databases, read environment, start tasks, access providers, or perform HTTP.
SPECS = (
    CommandSpec(
        "account.create",
        AccountCreate,
        "accounts",
        lambda s, c, p, r: ledger.create_account(p, s, c),
        currency_path="currency",
    ),
    CommandSpec(
        "account.edit",
        AccountPatch,
        "accounts",
        lambda s, c, p, r: ledger.patch_account(r, p, s, c),
        "account",
        True,
    ),
    CommandSpec(
        "transaction.create",
        TransactionCreate,
        "transactions",
        lambda s, c, p, r: ledger.record_transaction(s, c, p),
        account_field="account_id",
    ),
    CommandSpec(
        "transaction.edit",
        TransactionPatch,
        "transactions",
        lambda s, c, p, r: ledger.patch_transaction(r, p, s, c),
        "transaction",
        True,
    ),
    CommandSpec(
        "budget.create",
        BudgetInput,
        "budgets",
        lambda s, c, p, r: planning.save_budget(s, c, p),
        currency_path="currency",
    ),
    CommandSpec(
        "budget.edit",
        BudgetInput,
        "budgets",
        lambda s, c, p, r: planning.save_budget(s, c, p, r),
        "budget",
        True,
    ),
    CommandSpec(
        "bill.create",
        BillInput,
        "budgets",
        lambda s, c, p, r: planning.save_bill(s, c, p),
        currency_path="currency",
        account_field="account_id",
    ),
    CommandSpec(
        "bill.edit",
        BillInput,
        "budgets",
        lambda s, c, p, r: planning.save_bill(s, c, p, r),
        "bill",
        True,
        account_field="account_id",
    ),
    CommandSpec(
        "goal.create",
        GoalInput,
        "goals",
        lambda s, c, p, r: planning.save_goal(s, c, p),
        currency_path="currency",
    ),
    CommandSpec(
        "goal.edit",
        GoalInput,
        "goals",
        lambda s, c, p, r: planning.save_goal(s, c, p, r),
        "goal",
        True,
    ),
    CommandSpec(
        "goal.allocate",
        AllocationInput,
        "goals",
        lambda s, c, p, r: planning.allocate_goal(s, c, r, p),
        "goal",
        operation="allocate",
    ),
    CommandSpec(
        "scenario.create",
        ScenarioInput,
        "scenarios",
        lambda s, c, p, r: planning.save_scenario(s, c, p),
        currency_path="inputs.currency",
    ),
    CommandSpec(
        "holding.create",
        investing.HoldingCreate,
        "investments",
        lambda s, c, p, r: investing.create_holding(s, c, p),
        currency_path="currency",
    ),
    CommandSpec(
        "holding.edit",
        investing.HoldingUpdate,
        "investments",
        lambda s, c, p, r: investing.update_holding(s, c, r, p),
        "holding",
        True,
    ),
    CommandSpec(
        "credit.create",
        CreditAccount,
        "credit",
        lambda s, c, p, r: credit.add_account(p, store=s, context=c),
        currency_path="currency",
    ),
    CommandSpec(
        "credit.edit",
        CreditAccount,
        "credit",
        lambda s, c, p, r: credit.update_account(r, p, store=s, context=c),
        "credit",
        True,
    ),
    CommandSpec(
        "tax.organizer.create",
        Organizer,
        "tax-estate",
        lambda s, c, p, r: tax_estate.add_organizer(p, store=s, context=c),
        currency_path="currency",
    ),
    CommandSpec(
        "tax.scenario",
        TaxScenario,
        "tax-estate",
        lambda s, c, p, r: tax_estate.tax_scenario(p, store=s, context=c),
        operation="calculate",
        parent=("organizer", "organizer_id"),
    ),
    CommandSpec(
        "estate.asset.create",
        EstateAsset,
        "tax-estate",
        lambda s, c, p, r: tax_estate.add_asset(p, store=s, context=c),
        currency_path="currency",
    ),
    CommandSpec(
        "estate.contact.create",
        Contact,
        "tax-estate",
        lambda s, c, p, r: tax_estate.add_contact(p, store=s, context=c),
    ),
    CommandSpec(
        "estate.beneficiaries.set",
        Beneficiaries,
        "tax-estate",
        lambda s, c, p, r: tax_estate.set_beneficiaries(r, p, store=s, context=c),
        "estate_asset",
        operation="allocate",
    ),
    CommandSpec(
        "tax.item.create",
        TaxItem,
        "tax-estate",
        lambda s, c, p, r: tax_estate.add_tax_item(p, store=s, context=c),
        parent=("organizer", "organizer_id"),
    ),
    CommandSpec(
        "estate.document.create",
        Document,
        "tax-estate",
        lambda s, c, p, r: tax_estate.add_document(p, store=s, context=c),
    ),
    CommandSpec(
        "estate.checklist.create",
        Checklist,
        "tax-estate",
        lambda s, c, p, r: tax_estate.add_checklist(p, store=s, context=c),
    ),
    CommandSpec(
        "investing.recurring.create",
        investing.RecurringPlanCreate,
        "investments",
        lambda s, c, p, r: investing.create_recurring_plan(s, c, p),
        parent=("simulation_book", "book_id"),
        execution=CommandExecution(
            scope="scheduled_paper", scheduled_after_confirmation=True
        ),
        review_fields=("name",),
    ),
    CommandSpec(
        "bill.payment.record",
        PayInput,
        "transactions",
        _record_bill_payment,
        reference="bill",
        account_field="account_id",
        execution=CommandExecution(scope="recorded_bill_payment"),
        review_fields=("name", "amount", "account_id"),
        reference_page="budgets",
    ),
    CommandSpec("memory.create", MemoryWrite, "settings", _memory_create),
    CommandSpec("memory.edit", MemoryWrite, "settings", _memory_edit, "memory", True),
)
REGISTRY = {spec.name: spec for spec in SPECS}
if len(REGISTRY) != len(SPECS):
    raise RuntimeError("Duplicate finance command declaration")


def _target(spec, record_id=None, *, proposal=False):
    query = {"record_id": record_id} if record_id else {}
    if record_id and spec.name.startswith("account."):
        query["account_id"] = record_id
    if spec.name.startswith("estate."):
        query["tab"] = "estate"
    elif spec.name.startswith("tax."):
        query["tab"] = "tax"
    elif spec.name.startswith("memory."):
        query.update(section="data", panel="memories")
    return CommandTarget(
        page=spec.reference_page if proposal and spec.reference_page else spec.page,
        record_id=record_id,
        query=query,
    )


def catalog() -> list[CommandDeclaration]:
    return [
        CommandDeclaration(
            name=spec.name,
            title_key=spec.name,
            description=(
                f"{spec.name}: schedules fictional paper investments after confirmation; never real money execution."
                if spec.execution.scope == "scheduled_paper"
                else f"{spec.name}: local record only; review and confirmation required."
            ),
            input_schema=spec.input_model.model_json_schema(),
            target_page=spec.page,
            target_query=_target(spec).query,
            execution=spec.execution,
        )
        for spec in SPECS
    ]


def initialize(store: Store):
    with store.connection(write=True) as connection:
        connection.executescript(SCHEMA)


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _digest(value):
    return hashlib.sha256(_encoded(value).encode()).hexdigest()


def _spec(name):
    try:
        return REGISTRY[name]
    except KeyError:
        raise PlatformError("unsupported_finance_command") from None


def _read(store, context, kind, record_id):
    with store.connection() as connection:
        if kind == "account":
            value = ledger.account_balance(connection, context.household_id, record_id)
            return {
                key: val
                for key, val in value.items()
                if key not in ("balance", "balance_minor")
            }
        if kind == "transaction":
            return ledger._transaction_response(connection, context, record_id)
        if kind in ("budget", "bill", "goal"):
            value = planning._plan(connection, context, record_id, kind)
            if value["status"] == "archived":
                raise PlatformError("planning_record_archived", 409)
            return value
        if kind == "simulation_book":
            row = connection.execute(
                "SELECT * FROM p_investment_books WHERE id=? AND household_id=?",
                (record_id, context.household_id),
            ).fetchone()
            if row is None:
                raise PlatformError("simulation_book_not_found", 404)
            return investing._book_record(row)
        if kind == "bundle":
            return investing._bundle(record_id)
        if kind == "holding":
            return investing.get_holding(store, context, record_id)
        tables = {
            "credit": "p_credit_accounts",
            "organizer": "p_tax_organizers",
            "estate_asset": "p_estate_assets",
            "contact": "p_estate_contacts",
        }
        if kind in tables:
            return record(connection, tables[kind], context.household_id, record_id)
        if kind == "tax_items":
            rows = connection.execute(
                "SELECT document FROM p_tax_items WHERE household_id=? ORDER BY id LIMIT 5001",
                (context.household_id,),
            ).fetchall()
            if len(rows) > 5000:
                raise PlatformError("command_dependency_limit")
            return {
                "items": [
                    value
                    for row in rows
                    if (value := json.loads(row[0]))["organizer_id"] == record_id
                ]
            }
        if kind == "memory":
            row = connection.execute(
                "SELECT id,content,created_at,updated_at FROM p_memories WHERE id=? AND household_id=? AND user_id=?",
                (record_id, context.household_id, context.user_id),
            ).fetchone()
            if row:
                return dict(row)
            raise PlatformError("memory_not_found", 404)
    raise PlatformError("unsupported_command_reference")


def _fingerprint_record(kind, value):
    # Account balances may legitimately move between proposal and confirmation;
    # currency, ownership and metadata are the dependency, not a second balance.
    if kind == "account":
        value = {key: val for key, val in value.items() if key != "source"}
    elif kind == "simulation_book":
        value = {key: val for key, val in value.items() if key != "cash"}
    return _digest(value)


def _path_get(document, path):
    value = document
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _path_set(document, path, value):
    keys = path.split(".")
    for key in keys[:-1]:
        document = document.setdefault(key, {})
    document[keys[-1]] = value


def _merge(original, changes):
    result = deepcopy(original)
    for key, value in changes.items():
        result[key] = (
            _merge(result[key], value)
            if isinstance(value, dict) and isinstance(result.get(key), dict)
            else deepcopy(value)
        )
    return result


def _source(kind="user", title="Recorded local finance inputs"):
    return Evidence(
        id=identifier("source"),
        kind=kind,
        title=title,
        as_of=now().date(),
        recorded_at=now(),
    )


def _fields(arguments, currency=None, prefix=""):
    result = []
    for key, value in arguments.items():
        if key in ("idempotency_key", "record_id") or value is None:
            continue
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.extend(_fields(value, currency, name))
        elif isinstance(value, list):
            summary = [
                ", ".join(f"{k}: {v}" for k, v in row.items())
                if isinstance(row, dict)
                else str(row)
                for row in value
            ]
            result.append(CommandField(key=name, value=summary, kind="list"))
        else:
            monetary = key in {
                "amount",
                "opening_balance",
                "limit",
                "target_amount",
                "monthly_contribution",
                "monthly_withdrawal",
                "initial_balance",
                "total_cost",
                "value",
                "balance",
                "credit_limit",
                "minimum_payment",
                "ending_balance",
                "real_ending_balance",
                "scenario_amount",
                "income",
                "expenses",
                "net_amount",
            }
            result.append(
                CommandField(
                    key=name,
                    value=value,
                    kind="money"
                    if monetary
                    else "date"
                    if key.endswith(("date", "_on"))
                    else "number"
                    if isinstance(value, (int, float))
                    else "text",
                    currency=currency if monetary else None,
                )
            )
    return result


def _invoke(callback, store, context, artifact):
    if callback is None:
        return
    if inspect.iscoroutinefunction(callback):
        raise PlatformError("async_command_callback_forbidden")
    result = callback(store, context, artifact)
    if inspect.isawaitable(result):
        if inspect.iscoroutine(result):
            result.close()
        raise PlatformError("async_command_callback_forbidden")


class CommandService:
    def __init__(self, store: Store):
        self.store = store

    def inspect_currency(self, context, command_name, args, *, currency_context=None):
        """Read normalized currency through the same owner used by preparation."""
        with self.store.read_snapshot():
            with self.store.connection() as connection:
                assert_active_context(connection, context, minimum_role="viewer")
            return self._inspect_currency(
                context, _spec(command_name), args, currency_context
            )

    def _inspect_currency(self, context, spec, args, currency_context):
        try:
            return self._normalize(
                self.store, context, spec, args, "inspection", currency_context
            )[2]
        except (ValidationError, KeyError, TypeError, ValueError) as error:
            raise PlatformError("invalid_command_arguments") from error

    def inspect_revision(self, context, proposal_id, revision, changes):
        with self.store.read_snapshot():
            with self.store.connection() as connection:
                assert_active_context(connection, context, minimum_role="viewer")
                row = self._get_row(connection, context, proposal_id)
                self._validate_authority(row, context, revision)
                proposal = self._proposal(row)
                self._validate_pending(proposal)
            args, currency_context, inherited = self._revision_inputs(proposal, changes)
            currencies = self._inspect_currency(
                context, _spec(proposal.command_name), args, currency_context
            )
            return self._inherit_currencies(currencies, inherited)

    @staticmethod
    def _revision_inputs(proposal, changes):
        if not isinstance(changes, dict):
            raise PlatformError("invalid_command_arguments")
        spec = _spec(proposal.command_name)
        currency_changed = bool(
            spec.currency_path and _path_get(changes, spec.currency_path) is not None
        )
        inherited = None if currency_changed else proposal.currency
        currency_context = None
        if inherited and inherited[0].kind == "account":
            currency_context = {
                "kind": "account",
                "account_id": inherited[0].record_id,
                "code": inherited[0].code,
            }
        return _merge(proposal.arguments, changes), currency_context, inherited

    @staticmethod
    def _inherit_currencies(currencies, inherited):
        if not inherited:
            return currencies
        return [
            next(
                (
                    prior
                    for prior in inherited
                    if prior.code == value.code
                    and prior.record_id == value.record_id
                ),
                value,
            )
            for value in currencies
        ]

    def _normalize(self, store, context, spec, arguments, request_id, currency_context):
        raw = deepcopy(arguments)
        if not isinstance(raw, dict) or len(_encoded(raw).encode()) > MAX_ARGUMENT_BYTES:
            raise PlatformError("invalid_command_arguments")
        dependencies, currencies = [], []

        def dependency(kind, record_id):
            value = _read(store, context, kind, record_id)
            dependencies.append(
                {
                    "kind": kind,
                    "record_id": record_id,
                    "digest": _fingerprint_record(kind, value),
                    "evidence": value.get("source") or value.get("evidence"),
                }
            )
            return value

        original = (
            dependency(spec.reference, raw.get("record_id")) if spec.reference else None
        )
        target = raw.get("record_id")
        values = (
            raw.get("changes" if spec.edit else "values", {}) if spec.reference else raw
        )
        if not isinstance(values, dict):
            raise PlatformError("invalid_command_arguments")
        # Validate partial keys before merging with the immutable original values.
        if spec.edit:
            spec.input_model.model_validate(raw)
            values = _merge(
                {
                    key: original[key]
                    for key in spec.model.model_fields
                    if key in original
                },
                values,
            )
        elif spec.reference:
            spec.input_model.model_validate(raw)
        if spec.parent:
            kind, field = spec.parent
            original = dependency(kind, values.get(field))
            target = values.get(field)
        account_id = (
            (values.get(spec.account_field) or (original or {}).get(spec.account_field))
            if spec.account_field
            else None
        )
        account = dependency("account", account_id) if account_id else None
        if (
            spec.parent
            and spec.parent[0] == "simulation_book"
            and values.get("bundle_id")
        ):
            bundle = dependency("bundle", values["bundle_id"])
            if bundle["currency"] != original["currency"]:
                raise PlatformError("command_currency_mismatch")
        if values.get("to_account_id"):
            destination = dependency("account", values["to_account_id"])
            if account and destination["currency"] != account["currency"]:
                raise PlatformError("command_currency_mismatch")
        if spec.name == "goal.allocate":
            for allocation in values.get("allocations", []):
                owned = dependency("account", allocation["account_id"])
                if owned["currency"] != original["currency"]:
                    raise PlatformError("command_currency_mismatch")
        if spec.name == "estate.beneficiaries.set":
            for share in values.get("shares", []):
                dependency("contact", share["contact_id"])
        if spec.name == "tax.scenario":
            dependency("tax_items", values.get("organizer_id"))
        currency = (
            account.get("currency")
            if account
            else original.get("currency")
            if original
            else None
        )
        if currency:
            if values.get("currency") not in (None, currency):
                raise PlatformError("command_currency_mismatch")
            if "currency" in spec.model.model_fields:
                values["currency"] = currency
            currencies.append(
                CommandCurrency(
                    kind="account" if account else "record",
                    code=currency,
                    record_id=account["id"] if account else target,
                    source_id=(account.get("source", {}).get("id") if account else None),
                )
            )
        supplied = _path_get(values, spec.currency_path) if spec.currency_path else None
        if currency_context is not None:
            if not isinstance(currency_context, dict) or set(currency_context) - {
                "kind",
                "code",
                "account_id",
            }:
                raise PlatformError("invalid_currency_context")
            if currency_context.get("kind") == "account":
                selected = dependency("account", currency_context.get("account_id"))
                selected_currency = selected["currency"]
                if currency_context.get("code") not in (None, selected_currency):
                    raise PlatformError("command_currency_mismatch")
            elif currency_context.get("kind") in ("explicit", "ui_default"):
                selected_currency = currency_context.get("code")
            else:
                raise PlatformError("invalid_currency_context")
            if (currency and currency != selected_currency) or (
                supplied and supplied != selected_currency
            ):
                raise PlatformError("command_currency_mismatch")
            if currency_context.get("kind") == "account" and not currencies:
                currencies.append(
                    CommandCurrency(
                        kind="account",
                        code=selected_currency,
                        record_id=selected["id"],
                        source_id=selected.get("source", {}).get("id"),
                    )
                )
            if spec.currency_path and _path_get(values, spec.currency_path) is None:
                _path_set(values, spec.currency_path, selected_currency)
        if spec.currency_path:
            selected_currency = _path_get(values, spec.currency_path)
            if not selected_currency:
                raise PlatformError("command_currency_required")
            if currency and selected_currency != currency:
                raise PlatformError("command_currency_mismatch")
            currency = selected_currency
            if not currencies:
                currencies.append(
                    CommandCurrency(
                        kind=(
                            "ui_default"
                            if currency_context
                            and currency_context.get("kind") == "ui_default"
                            and not supplied
                            else "explicit"
                        ),
                        code=currency,
                        stated_request_id=(
                            request_id
                            if not currency_context
                            or currency_context.get("kind") != "ui_default"
                            or supplied
                            else None
                        ),
                    )
                )
        if currency:
            minor_units(Decimal(0), currency)
        if "idempotency_key" in values:
            raise PlatformError("server_owned_command_identity")
        if not spec.reference:
            spec.input_model.model_validate(values)
        domain_values = {**values}
        if "idempotency_key" in spec.model.model_fields:
            domain_values["idempotency_key"] = "command-normalization"
        payload = spec.model.model_validate(domain_values)
        normalized = payload.model_dump(mode="json", exclude={"idempotency_key"})
        if currency:

            def check_money(value):
                for key, item in value.items():
                    if isinstance(item, dict):
                        check_money(item)
                    elif isinstance(item, list):
                        for child in item:
                            if isinstance(child, dict):
                                check_money(child)
                    elif (
                        key in {"amount", "opening_balance", "total_cost"}
                        and item is not None
                    ):
                        minor_units(Decimal(item), currency)

            check_money(normalized)
        if spec.reference:
            normalized = {
                "record_id": target,
                ("changes" if spec.edit else "values"): normalized,
            }
        return normalized, dependencies, currencies, target

    def record_choices(self, context, limit=30, kind=None):
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise PlatformError("invalid_record_choice_limit")
        choices = {
            "account": ("p_accounts", "name", "currency", " AND deleted_at IS NULL"),
            "transaction": (
                "p_transactions",
                "merchant",
                "currency",
                " AND deleted_at IS NULL",
            ),
            "budget": (
                "p_plans",
                "json_extract(document,'$.category')",
                "json_extract(document,'$.currency')",
                " AND kind='budget' AND status!='archived'",
            ),
            "bill": (
                "p_plans",
                "json_extract(document,'$.name')",
                "json_extract(document,'$.currency')",
                " AND kind='bill' AND status!='archived'",
            ),
            "goal": (
                "p_plans",
                "json_extract(document,'$.name')",
                "json_extract(document,'$.currency')",
                " AND kind='goal' AND status!='archived'",
            ),
            "simulation_book": ("p_investment_books", "name", "currency", ""),
            "holding": (
                "p_investment_holdings",
                "name",
                "currency",
                " AND deleted_at IS NULL",
            ),
            "credit": (
                "p_credit_accounts",
                "json_extract(document,'$.name')",
                "json_extract(document,'$.currency')",
                "",
            ),
            "organizer": (
                "p_tax_organizers",
                "json_extract(document,'$.country') || ' ' || json_extract(document,'$.year')",
                "json_extract(document,'$.currency')",
                "",
            ),
            "estate_asset": (
                "p_estate_assets",
                "json_extract(document,'$.name')",
                "json_extract(document,'$.currency')",
                "",
            ),
            "contact": (
                "p_estate_contacts",
                "json_extract(document,'$.name')",
                "NULL",
                "",
            ),
            "memory": ("p_memories", "substr(content,1,120)", "NULL", " AND user_id=?"),
        }
        if kind is not None and kind not in choices:
            raise PlatformError("unsupported_command_reference")
        groups = []
        with self.store.connection() as connection:
            assert_active_context(connection, context, minimum_role="viewer")
            for record_kind, (table, name, currency, condition) in choices.items():
                if kind is not None and kind != record_kind:
                    continue
                parameters = (
                    (context.household_id, context.user_id, limit + 1)
                    if record_kind == "memory"
                    else (context.household_id, limit + 1)
                )
                rows = connection.execute(
                    f"SELECT id,{name} AS name,{currency} AS currency FROM {table} WHERE household_id=?{condition} ORDER BY rowid DESC LIMIT ?",
                    parameters,
                ).fetchall()
                groups.append(
                    [
                        {
                            "id": row["id"],
                            "kind": record_kind,
                            "name": row["name"],
                            "currency": row["currency"],
                        }
                        for row in rows
                    ]
                )
        # Interleave kinds so a large ledger cannot hide the other artifact types.
        items = [
            group[index]
            for index in range(limit + 1)
            for group in groups
            if len(group) > index
        ]
        return {"items": items[:limit], "limit": limit, "has_more": len(items) > limit}

    def resolve_record(self, context, kind, record_id):
        with self.store.read_snapshot():
            with self.store.connection() as connection:
                assert_active_context(connection, context, minimum_role="viewer")
            return _read(self.store, context, kind, record_id)

    @staticmethod
    def _execution_fields(spec):
        if spec.execution.scope == "local_record":
            return []
        return [
            field.model_copy(update={"editable": False})
            for field in _fields(
                spec.execution.model_dump(mode="json"), prefix="execution"
            )
        ]

    def _review_fields(self, store, context, spec, arguments, currencies, target):
        currency = currencies[0].code if currencies else None
        fields = _fields(arguments, currency)
        if spec.review_fields:
            kind = spec.reference or spec.parent[0]
            original = _read(store, context, kind, target)
            fields.extend(
                field.model_copy(update={"editable": False})
                for field in _fields(
                    {key: original[key] for key in spec.review_fields},
                    currency,
                    "reference",
                )
            )
        fields.extend(self._execution_fields(spec))
        return fields

    def _get_row(self, connection, context, proposal_id):
        row = connection.execute(
            "SELECT * FROM p_command_proposals WHERE id=? AND household_id=? AND user_id=?",
            (proposal_id, context.household_id, context.user_id),
        ).fetchone()
        if row is None:
            raise PlatformError("proposal_not_found", 404)
        return row

    @staticmethod
    def _proposal(row):
        return Proposal.model_validate(
            {**json.loads(row["document"]), "status": row["status"]}
        )

    def get(self, context, proposal_id):
        with self.store.connection() as connection:
            return self._proposal(self._get_row(connection, context, proposal_id))

    def read_for_conversation(self, context, proposal_id, conversation_id):
        """Project an artifact after the chat owner has authorized its conversation."""
        with self.store.connection() as connection:
            assert_active_context(connection, context, minimum_role="viewer")
            row = connection.execute(
                "SELECT * FROM p_command_proposals WHERE id=? AND household_id=? AND conversation_id=?",
                (proposal_id, context.household_id, conversation_id),
            ).fetchone()
            if row is None:
                raise PlatformError("proposal_not_found", 404)
            return self._proposal(row)

    def current(self, context, conversation_id):
        with self.store.connection() as connection:
            row = connection.execute(
                "SELECT * FROM p_command_proposals WHERE household_id=? AND user_id=? AND conversation_id=? AND status='pending' ORDER BY revision DESC LIMIT 1",
                (context.household_id, context.user_id, conversation_id),
            ).fetchone()
            return self._proposal(row) if row else None

    def prepare(
        self,
        context,
        command_name,
        args,
        conversation_id,
        request_id,
        currency_context=None,
        *,
        on_proposal=None,
    ):
        if not all(
            isinstance(value, str) and 1 <= len(value) <= 160
            for value in (conversation_id, request_id)
        ):
            raise PlatformError("invalid_command_identity")
        with self.store.transaction() as bound:
            return self._prepare(
                bound,
                context,
                command_name,
                args,
                conversation_id,
                request_id,
                currency_context,
                on_proposal,
            )

    def _prepare(
        self,
        bound,
        context,
        command_name,
        args,
        conversation_id,
        request_id,
        currency_context,
        on_proposal,
        inherited_currency=None,
    ):
        spec = _spec(command_name)
        with bound.connection(write=True) as connection:
            assert_active_context(connection, context)
            try:
                fingerprint = _digest(
                    {
                        "command": command_name,
                        "args": args,
                        "currency_context": currency_context,
                    }
                )
            except (TypeError, ValueError) as error:
                raise PlatformError("invalid_command_arguments") from error
            existing = connection.execute(
                "SELECT * FROM p_command_proposals WHERE household_id=? AND conversation_id=? AND request_id=?",
                (context.household_id, conversation_id, request_id),
            ).fetchone()
            if existing:
                if (
                    existing["request_hash"] != fingerprint
                    or existing["user_id"] != context.user_id
                ):
                    raise PlatformError("command_request_conflict", 409)
                return self._proposal(existing)
            try:
                normalized, dependencies, currencies, target = self._normalize(
                    bound, context, spec, args, request_id, currency_context
                )
            except (ValidationError, KeyError, TypeError, ValueError) as error:
                raise PlatformError("invalid_command_arguments") from error
            currencies = self._inherit_currencies(currencies, inherited_currency)
            revision = connection.execute(
                "SELECT COALESCE(MAX(revision),0)+1 FROM p_command_proposals WHERE household_id=? AND conversation_id=?",
                (context.household_id, conversation_id),
            ).fetchone()[0]
            proposal_id = identifier("proposal")
            proposal = Proposal(
                proposal_id=proposal_id,
                conversation_id=conversation_id,
                command_name=command_name,
                revision=revision,
                status="pending",
                title_key=spec.name,
                fields=self._review_fields(
                    bound, context, spec, normalized, currencies, target
                ),
                execution=spec.execution,
                arguments=normalized,
                currency=currencies,
                evidence=[
                    _source(),
                    *[
                        Evidence.model_validate(dep["evidence"])
                        for dep in dependencies
                        if dep.get("evidence")
                    ],
                ],
                target=_target(spec, target, proposal=True),
                created_at=now(),
                expires_at=now() + PROPOSAL_TTL,
            )
            connection.execute(
                "UPDATE p_command_proposals SET status='superseded' WHERE household_id=? AND conversation_id=? AND status='pending'",
                (context.household_id, conversation_id),
            )
            connection.execute(
                "INSERT INTO p_command_proposals VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    proposal_id,
                    context.household_id,
                    context.user_id,
                    conversation_id,
                    request_id,
                    fingerprint,
                    command_name,
                    revision,
                    context.data_generation,
                    context.role,
                    "pending",
                    proposal.model_dump_json(),
                    _encoded(dependencies),
                ),
            )
            _invoke(on_proposal, bound, context, proposal)
            return proposal

    def confirm(self, context, proposal_id, revision, *, on_receipt=None):
        with self.store.transaction() as bound:
            with bound.connection(write=True) as connection:
                assert_active_context(connection, context)
                row = self._get_row(connection, context, proposal_id)
                proposal = self._proposal(row)
                self._validate_authority(row, context, revision)
                if row["status"] == "consumed":
                    saved = connection.execute(
                        "SELECT document FROM p_command_receipts WHERE proposal_id=? AND household_id=?",
                        (proposal_id, context.household_id),
                    ).fetchone()
                    return CommandReceipt.model_validate_json(saved[0])
                self._validate_pending(proposal)
                for dependency in json.loads(row["dependencies"]):
                    current = _read(
                        bound, context, dependency["kind"], dependency["record_id"]
                    )
                    if (
                        _fingerprint_record(dependency["kind"], current)
                        != dependency["digest"]
                    ):
                        raise PlatformError("proposal_dependency_changed", 409)
                spec = _spec(proposal.command_name)
                args = proposal.arguments
                values = (
                    args["changes" if spec.edit else "values"] if spec.reference else args
                )
                if "idempotency_key" in spec.model.model_fields:
                    values = {**values, "idempotency_key": f"command:{proposal_id}"}
                payload = spec.model.model_validate(values)
                result = spec.handler(bound, context, payload, args.get("record_id"))
                if inspect.isawaitable(result):
                    if inspect.iscoroutine(result):
                        result.close()
                    raise PlatformError("async_command_handler_forbidden")
                record_id = result.get("id")
                if not isinstance(record_id, str) or not record_id:
                    raise PlatformError("command_artifact_missing", 500)
                summary = result.get("result", result)
                visible = {
                    key: value
                    for key, value in summary.items()
                    if not isinstance(value, (dict, list))
                    and key
                    not in (
                        "id",
                        "household_id",
                        "user_id",
                        "created_by",
                        "status",
                        "method",
                        "recorded_at",
                        "created_at",
                        "updated_at",
                    )
                }
                evidence = result.get("evidence") or result.get("source")
                sources = (
                    [Evidence.model_validate(evidence)]
                    if evidence
                    else [
                        _source("calculated" if spec.operation == "calculate" else "user")
                    ]
                )
                receipt = CommandReceipt(
                    receipt_id=identifier("command-receipt"),
                    proposal_id=proposal_id,
                    conversation_id=proposal.conversation_id,
                    command_name=spec.name,
                    revision=revision,
                    title_key=spec.name,
                    fields=_fields(
                        visible, proposal.currency[0].code if proposal.currency else None
                    )
                    + self._execution_fields(spec),
                    evidence=sources,
                    target=_target(spec, record_id),
                    execution=spec.execution,
                    record_id=record_id,
                    created_at=now(),
                )
                connection.execute(
                    "INSERT INTO p_command_receipts VALUES(?,?,?,?)",
                    (
                        receipt.receipt_id,
                        context.household_id,
                        proposal_id,
                        receipt.model_dump_json(),
                    ),
                )
                connection.execute(
                    "UPDATE p_command_proposals SET status='consumed' WHERE id=?",
                    (proposal_id,),
                )
                _invoke(on_receipt, bound, context, receipt)
                return receipt

    @staticmethod
    def _validate_authority(row, context, revision):
        if row["revision"] != revision:
            raise PlatformError("proposal_revision_changed", 409)
        if row["data_generation"] != context.data_generation:
            raise PlatformError("household_data_changed", 409)
        if row["role"] != context.role:
            raise PlatformError("household_access_changed", 409)

    @staticmethod
    def _validate_pending(proposal):
        if proposal.status != "pending":
            raise PlatformError("proposal_not_pending", 409)
        if proposal.expires_at <= now():
            raise PlatformError("proposal_expired", 409)

    def revise(
        self, context, proposal_id, revision, changes, *, request_id, on_proposal=None
    ):
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 160:
            raise PlatformError("invalid_command_identity")
        with self.store.transaction() as bound:
            with bound.connection(write=True) as connection:
                assert_active_context(connection, context)
                row = self._get_row(connection, context, proposal_id)
                self._validate_authority(row, context, revision)
                proposal = self._proposal(row)
                existing = connection.execute(
                    "SELECT id FROM p_command_proposals WHERE household_id=? AND conversation_id=? AND request_id=?",
                    (context.household_id, proposal.conversation_id, request_id),
                ).fetchone()
                if existing is None:
                    self._validate_pending(proposal)
                arguments, currency_context, inherited = self._revision_inputs(
                    proposal, changes
                )
                return self._prepare(
                    bound,
                    context,
                    proposal.command_name,
                    arguments,
                    proposal.conversation_id,
                    request_id,
                    currency_context,
                    on_proposal,
                    inherited_currency=inherited,
                )

    def cancel(self, context, proposal_id, revision):
        with self.store.transaction() as bound:
            with bound.connection(write=True) as connection:
                assert_active_context(connection, context)
                row = self._get_row(connection, context, proposal_id)
                self._validate_authority(row, context, revision)
                proposal = self._proposal(row)
                if proposal.status == "cancelled":
                    return proposal
                self._validate_pending(proposal)
                connection.execute(
                    "UPDATE p_command_proposals SET status='cancelled' WHERE id=?",
                    (proposal_id,),
                )
                return proposal.model_copy(update={"status": "cancelled"})


def export_data(connection, context):
    return {
        table: [
            dict(row)
            for row in connection.execute(
                f"SELECT * FROM {table} WHERE household_id=?", (context.household_id,)
            )
        ]
        for table in ("p_command_proposals", "p_command_receipts")
    }


def clear_data(connection, context):
    connection.execute(
        "DELETE FROM p_command_receipts WHERE household_id=?", (context.household_id,)
    )
    connection.execute(
        "DELETE FROM p_command_proposals WHERE household_id=?", (context.household_id,)
    )


def usage_data(connection, context):
    return {
        "proposals": connection.execute(
            "SELECT COUNT(*) FROM p_command_proposals WHERE household_id=?",
            (context.household_id,),
        ).fetchone()[0],
        "receipts": connection.execute(
            "SELECT COUNT(*) FROM p_command_receipts WHERE household_id=?",
            (context.household_id,),
        ).fetchone()[0],
    }
