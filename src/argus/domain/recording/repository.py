"""Storage seam for accounts and openings, plus the in-memory twin.

The repository owns atomic storage facts: idempotent creation, version and
revision compare-and-set, and the account/record/revision write in one step.
Validation and product rules stay in the domain modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argus.domain.recording.assets import AssetDetailsResult
    from argus.domain.recording.loop_storage import OperationResult, Planner

import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from argus.domain.recording.accounts import AccountFacts
from argus.domain.recording.asset_model import AssetChange
from argus.domain.recording.asset_schemas import AssetDetailsRequest
from argus.domain.recording.errors import (
    AccountNotFound,
    IdempotencyConflict,
    StaleVersion,
)
from argus.domain.recording.loop import CheckRecord, Coverage, ExpenseRecord
from argus.domain.recording.records import OpeningRecord, OpeningRevision, OpeningWrite

CREATE_SCOPE = "financial_accounts.create"


@dataclass(frozen=True)
class NewAccount:
    type: str
    currency: str
    nickname: str | None
    ownership_share_bps: int


@dataclass(frozen=True)
class StoredAccount:
    account: AccountFacts
    opening: OpeningRecord | None
    expenses: tuple[ExpenseRecord, ...] = ()
    checks: tuple[CheckRecord, ...] = ()
    coverage: tuple[Coverage, ...] = ()
    related_debt_account_id: str | None = None
    asset_changes: tuple[AssetChange, ...] = ()

    @property
    def has_records(self) -> bool:
        return self.opening is not None or bool(self.expenses) or bool(self.checks)

    @property
    def has_activity(self) -> bool:
        return bool(self.expenses) or bool(self.checks)


@dataclass(frozen=True)
class CreateResult:
    stored: StoredAccount
    created: bool


class FinancialAccountRepository(Protocol):
    def write_asset_details(
        self,
        *,
        user_id: str,
        account_id: str,
        request: AssetDetailsRequest,
        idempotency_key: str,
        identity_hash: str,
    ) -> AssetDetailsResult: ...

    def mutate(
        self,
        *,
        user_id: str,
        account_id: str,
        idempotency_key: str,
        identity_hash: str,
        expected_version: int,
        planner: Planner,
    ) -> OperationResult: ...

    def create(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        identity_hash: str,
        account: NewAccount,
        opening: OpeningWrite | None,
    ) -> CreateResult: ...

    def list_accounts(self, *, user_id: str) -> list[StoredAccount]: ...

    def get_account(self, *, user_id: str, account_id: str) -> StoredAccount | None: ...

    def update_account(
        self,
        *,
        user_id: str,
        account_id: str,
        expected_version: int,
        changes: dict[str, object],
    ) -> StoredAccount: ...

    def write_opening(
        self,
        *,
        user_id: str,
        account_id: str,
        expected_revision: int | None,
        expected_version: int,
        write: OpeningWrite,
    ) -> StoredAccount: ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryFinancialAccountRepository:
    """Deterministic twin for ``ARGUS_PERSISTENCE_MODE=memory`` and unit tests."""

    def __init__(self, clock: Callable[[], datetime] = _utcnow) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._accounts: dict[str, StoredAccount] = {}
        self._money_receipts: dict[
            tuple[str, str | None, str], tuple[str, str, int, tuple[str, ...]]
        ] = {}
        self._operations: dict[tuple[str, str, str], tuple[str, str, int, str]] = {}
        self._reservations: dict[tuple[str, str, str], tuple[str, str]] = {}

    def create(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        identity_hash: str,
        account: NewAccount,
        opening: OpeningWrite | None,
    ) -> CreateResult:
        with self._lock:
            key = (user_id, CREATE_SCOPE, idempotency_key)
            reserved = self._reservations.get(key)
            if reserved is not None:
                existing_hash, account_id = reserved
                if existing_hash != identity_hash:
                    raise IdempotencyConflict()
                return CreateResult(self._accounts[account_id], created=False)
            now = self._clock()
            facts = AccountFacts(
                id=str(uuid4()),
                user_id=user_id,
                type=account.type,
                currency=account.currency,
                nickname=account.nickname,
                archived=False,
                ownership_share_bps=account.ownership_share_bps,
                version=1,
                created_at=now,
                updated_at=now,
            )
            record = None
            if opening is not None:
                record = OpeningRecord(
                    id=str(uuid4()),
                    account_id=facts.id,
                    revisions=(_revision(1, opening, user_id, now),),
                )
            stored = StoredAccount(facts, record)
            self._accounts[facts.id] = stored
            self._reservations[key] = (identity_hash, facts.id)
            return CreateResult(stored, created=True)

    def list_accounts(self, *, user_id: str) -> list[StoredAccount]:
        with self._lock:
            owned = [
                item
                for item in self._accounts.values()
                if item.account.user_id == user_id
            ]
        return sorted(owned, key=lambda item: (item.account.created_at, item.account.id))

    def get_account(self, *, user_id: str, account_id: str) -> StoredAccount | None:
        with self._lock:
            stored = self._accounts.get(account_id)
        if stored is None or stored.account.user_id != user_id:
            return None
        return stored

    def update_account(
        self,
        *,
        user_id: str,
        account_id: str,
        expected_version: int,
        changes: dict[str, object],
    ) -> StoredAccount:
        with self._lock:
            stored = self._owned(user_id, account_id)
            if stored.account.version != expected_version:
                raise StaleVersion()
            from argus.domain.recording.asset_storage import validate_type_change

            linked = stored.related_debt_account_id is not None or any(
                a.related_debt_account_id == account_id for a in self._accounts.values()
            )
            validate_type_change(stored, changes, linked)
            facts = replace(
                stored.account,
                **changes,
                version=stored.account.version + 1,
                updated_at=self._clock(),
            )
            updated = replace(stored, account=facts)
            self._accounts[account_id] = updated
            return updated

    def write_opening(
        self,
        *,
        user_id: str,
        account_id: str,
        expected_revision: int | None,
        expected_version: int,
        write: OpeningWrite,
    ) -> StoredAccount:
        with self._lock:
            stored = self._owned(user_id, account_id)
            current = stored.opening.current.revision if stored.opening else None
            if current != expected_revision or stored.account.version != expected_version:
                raise StaleVersion()
            now = self._clock()
            next_revision = (current or 0) + 1
            revision = _revision(next_revision, write, user_id, now)
            if stored.opening is None:
                record = OpeningRecord(str(uuid4()), account_id, (revision,))
            else:
                record = replace(
                    stored.opening, revisions=(*stored.opening.revisions, revision)
                )
            facts = replace(
                stored.account, version=stored.account.version + 1, updated_at=now
            )
            updated = replace(stored, account=facts, opening=record)
            self._accounts[account_id] = updated
            return updated

    def mutate(
        self,
        *,
        user_id: str,
        account_id: str,
        idempotency_key: str,
        identity_hash: str,
        expected_version: int,
        planner: Planner,
    ) -> OperationResult:
        from argus.domain.recording.loop_storage import OperationResult, apply

        with self._lock:
            stored = self._owned(user_id, account_id)
            key = (user_id, account_id, idempotency_key)
            receipt = self._operations.get(key)
            if receipt:
                identity, record_id, revision, kind = receipt
                if identity != identity_hash:
                    raise IdempotencyConflict()
                return OperationResult(stored, record_id, revision, kind, True)
            if stored.account.version != expected_version:
                raise StaleVersion()
            mutation = planner(stored)
            updated = apply(stored, mutation, self._clock())
            record = mutation.record
            revision = (
                record.revision
                if isinstance(record, CheckRecord)
                else record.current.revision
            )
            self._accounts[account_id] = updated
            self._operations[key] = (identity_hash, record.id, revision, mutation.kind)
            return OperationResult(updated, record.id, revision, mutation.kind, False)

    def write_asset_details(
        self,
        *,
        user_id: str,
        account_id: str,
        request: AssetDetailsRequest,
        idempotency_key: str,
        identity_hash: str,
    ) -> AssetDetailsResult:
        from argus.domain.recording.asset_storage import memory_write

        return memory_write(
            self,
            user_id=user_id,
            account_id=account_id,
            request=request,
            idempotency_key=idempotency_key,
            identity_hash=identity_hash,
        )

    def _owned(self, user_id: str, account_id: str) -> StoredAccount:
        stored = self._accounts.get(account_id)
        if stored is None or stored.account.user_id != user_id:
            raise AccountNotFound()
        return stored


def _revision(
    number: int, write: OpeningWrite, user_id: str, now: datetime
) -> OpeningRevision:
    return OpeningRevision(
        revision=number,
        amount_minor=write.amount_minor,
        as_of=write.as_of,
        time_zone=write.time_zone,
        reason=write.reason,
        recorded_by=user_id,
        recorded_at=now,
        estimate_basis=write.estimate_basis,
    )
