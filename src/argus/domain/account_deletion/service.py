"""The account deletion command (Lane 6).

Order, matching ``docs/specs/lanes/account-deletion-fk-census.md``:

1. Open or reuse the run. The run is keyed on a hash of the user id; the id
   itself is held only while the run is in flight, so a retry finds the same
   run and reuses the same placeholders.
2. Reserve one placeholder id per sharing scope the person's rows are pinned
   in (a household, or an activity group shared outside any plan), then
   create each placeholder through the Admin API. Ids are
   registered before the create, so the auth triggers already skip them.
3. One database transaction: steps 1.1 to 1.3 per household, archives passed
   on, sources captured for revocation and removed (2), invite ids forgotten
   (4), future responsibilities returned, each unit moved to its placeholder
   (5.1, 5.2), the person's own plans deleted (5.3), feedback stripped (6),
   then a check that nothing still holds the id.
4. The auth user is deleted through the Admin API (7); unused placeholders are
   deleted; the id and the placeholder map are scrubbed from the run.
5. Every provider token Cuadrao holds is revoked from the captured
   ciphertext: Plaid access tokens and Gmail (Google) refresh tokens. Apple is
   recorded as owed. PostHog person deletion (8) runs last. A provider that
   fails stays pending and the run stays ``auth_deleted`` until a retry
   clears it.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from loguru import logger

from argus.domain.account_deletion.auth_admin import AuthAdmin, placeholder_email
from argus.domain.household import deletion as household_deletion
from argus.observability.analytics_deletion import AnalyticsDeletion
from argus.observability.product_events import actor_hash_for_user

RunStatus = Literal["started", "data_deleted", "auth_deleted", "done"]
_ATTEMPTS = 3


class AccountDeletionRejected(Exception):
    """The request names no deletable account (bad id, guest, placeholder)."""


class AccountDeletionIncomplete(Exception):
    """The data step could not finish; the run stays resumable."""


class ProviderRevoker(Protocol):
    def revoke_for_deletion(
        self,
        *,
        source: str,
        connection_id: str,
        external_ref: str,
        envelope: bytes | None,
    ) -> str: ...


class AppleRevoker(Protocol):
    def revoke(self, *, identity_id: str) -> bool:
        """True only when Apple confirmed the revoke."""
        ...


class AppleRevocationUnavailable:
    """No Sign in with Apple revoke exists on this base: no Apple token is held.
    Fails safe: the Apple revocation stays pending on the run.

    TODO(#793): #793 adds ``apple_sign_in_credentials`` (``user_id`` ON DELETE
    RESTRICT) and a revoke function. When it lands, step 2 moves the stored
    token into the pending ``apple`` revocation (ciphertext, like Gmail and
    Plaid) and deletes that row before step 7, and this class is replaced by
    an adapter over #793's revoke function. The census must then cover the
    table too."""

    def revoke(self, *, identity_id: str) -> bool:
        return False


@dataclass
class DeletionOutcome:
    status: RunStatus
    pending: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


def subject_hash(user_id: str) -> str:
    return hashlib.sha256(f"argus:account-deletion:{user_id}".encode()).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _uuid(value: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise AccountDeletionRejected("invalid_user_id") from None


class AccountDeletionService:
    def __init__(
        self,
        *,
        households: Any,
        auth_admin: AuthAdmin,
        revoker: ProviderRevoker | None,
        analytics: AnalyticsDeletion,
        apple: AppleRevoker | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        # The household repository owns the pool and binds one connection per
        # context, so its leave helpers run inside this command's transaction.
        self._households = households
        self._auth = auth_admin
        self._revoker = revoker
        self._analytics = analytics
        self._apple = apple or AppleRevocationUnavailable()
        self._clock = clock

    # -- entry point -------------------------------------------------------------

    def delete_account(self, *, user_id: str) -> DeletionOutcome:
        user_id = _uuid(user_id)
        subject = subject_hash(user_id)
        run = self._open_run(user_id, subject)
        if run["status"] == "started":
            for attempt in range(_ATTEMPTS):
                self._reserve_placeholders(user_id, subject)
                try:
                    self._delete_data(user_id, subject)
                    break
                except _UnitsChanged:
                    if attempt == _ATTEMPTS - 1:
                        raise AccountDeletionIncomplete("units_changed") from None
            run["status"] = "data_deleted"
        if run["status"] == "data_deleted":
            self._delete_auth_user(user_id, subject)
            run["status"] = "auth_deleted"
        if run["status"] == "auth_deleted":
            return self._settle_external(subject)
        return DeletionOutcome(status="done", counts=run["steps"].get("counts", {}))

    # -- 1. the run --------------------------------------------------------------

    def _open_run(self, user_id: str, subject: str) -> dict[str, Any]:
        with self._households.connection() as connection, connection.transaction():
            row = connection.execute(
                "select status, steps from argus_private.account_deletion_runs"
                " where subject_hash = %s for update",
                (subject,),
            ).fetchone()
            if row is not None:
                return {"status": row[0], "steps": row[1] or {}}
            user = connection.execute(
                "select is_anonymous, raw_app_meta_data from auth.users where id = %s",
                (user_id,),
            ).fetchone()
            if user is None:
                raise AccountDeletionRejected("unknown_user")
            if user[0]:
                # A guest has no account to delete; the guest workspace has its own expiry.
                raise AccountDeletionRejected("guest")
            placeholder = connection.execute(
                "select argus_private.is_account_placeholder(%s, %s::jsonb)",
                (user_id, json.dumps(user[1] or {})),
            ).fetchone()[0]
            if placeholder:
                raise AccountDeletionRejected("placeholder")
            connection.execute(
                "insert into argus_private.account_deletion_runs"
                " (subject_hash, user_id, analytics_distinct_id, status)"
                " values (%s, %s, %s, 'started')",
                (subject, user_id, actor_hash_for_user(user_id)),
            )
            return {"status": "started", "steps": {}}

    # -- 2. placeholders ---------------------------------------------------------

    def _units(
        self, connection: Any, user_id: str
    ) -> dict[tuple[str, str], tuple[str, str]]:
        """Each plan or activity group the person's rows are pinned to, and the
        sharing scope whose placeholder it moves to: the plan's household, or
        the group itself when it is shared outside any plan."""
        return {
            (str(kind), str(unit)): (str(scope_kind), str(scope))
            for kind, unit, scope_kind, scope in connection.execute(
                "select unit_kind, unit_id, scope_kind, scope_id"
                " from argus_private.deletion_placeholder_units(%s)",
                (user_id,),
            ).fetchall()
        }

    def _reserve_placeholders(self, user_id: str, subject: str) -> None:
        with self._households.connection() as connection:
            with connection.transaction():
                scopes = set(self._units(connection, user_id).values())
                known = {
                    (str(kind), str(scope))
                    for kind, scope in connection.execute(
                        "select scope_kind, scope_id from argus_private.account_deletion_placeholders"
                        " where subject_hash = %s",
                        (subject,),
                    ).fetchall()
                }
                for kind, scope in sorted(scopes - known):
                    pid = str(uuid.uuid4())
                    # Registered before the Admin API create, so the auth
                    # triggers already skip it when it arrives.
                    connection.execute(
                        "insert into argus_private.account_placeholders (id) values (%s)",
                        (pid,),
                    )
                    connection.execute(
                        "insert into argus_private.account_deletion_placeholders"
                        " (subject_hash, scope_kind, scope_id, placeholder_id)"
                        " values (%s, %s, %s, %s)",
                        (subject, kind, scope, pid),
                    )
            pending = connection.execute(
                "select placeholder_id from argus_private.account_deletion_placeholders"
                " where subject_hash = %s and not created order by placeholder_id",
                (subject,),
            ).fetchall()
        for (pid,) in pending:
            pid = str(pid)
            if not self._auth.user_exists(pid):
                self._auth.create_placeholder(
                    user_id=pid, email=placeholder_email(str(uuid.uuid4()))
                )
            with self._households.connection() as connection, connection.transaction():
                connection.execute(
                    "update argus_private.account_deletion_placeholders set created = true"
                    " where placeholder_id = %s",
                    (pid,),
                )

    # -- 3. the data transaction -------------------------------------------------

    def _delete_data(self, user_id: str, subject: str) -> None:
        now = self._clock()
        apple = "apple" in self._auth.identity_providers(user_id)
        with self._households.connection() as connection:
            with connection.transaction():
                connection.execute(
                    "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"account_deletion:{user_id}",),
                )
                status = connection.execute(
                    "select status from argus_private.account_deletion_runs"
                    " where subject_hash = %s for update",
                    (subject,),
                ).fetchone()[0]
                if status != "started":
                    return
                connection.execute(
                    "select set_config('argus.locked_history_writer', 'deletion', true)"
                )
                scopes = {
                    (str(kind), str(scope)): str(pid)
                    for kind, scope, pid in connection.execute(
                        "select scope_kind, scope_id, placeholder_id"
                        " from argus_private.account_deletion_placeholders"
                        " where subject_hash = %s and created",
                        (subject,),
                    ).fetchall()
                }
                units = self._units(connection, user_id)
                if not set(units.values()) <= set(scopes):
                    # Something new was pinned since the reservation: roll back
                    # and reserve again rather than delete a row someone keeps.
                    raise _UnitsChanged()
                counts = self._delete_in_transaction(
                    connection,
                    user_id=user_id,
                    subject=subject,
                    units={unit: scopes[scope] for unit, scope in units.items()},
                    apple=apple,
                    now=now,
                )
                connection.execute(
                    "update argus_private.account_deletion_runs"
                    " set status = 'data_deleted', updated_at = %s,"
                    "     steps = steps || jsonb_build_object('counts', %s::jsonb)"
                    " where subject_hash = %s",
                    (now, json.dumps(counts), subject),
                )

    def _delete_in_transaction(
        self,
        connection: Any,
        *,
        user_id: str,
        subject: str,
        units: dict[tuple[str, str], str],
        apple: bool,
        now: datetime,
    ) -> dict[str, int]:
        # 1.1 to 1.3, and 5.2 for archives left by earlier departures.
        result = household_deletion.leave_every_household(
            connection, self._households, user_id=user_id, now=now
        )
        events = list(result.events)
        # 2: capture every provider credential, then remove the sources.
        captured = connection.execute(
            """insert into argus_private.account_deletion_revocations
                 (subject_hash, provider, source_ref, external_ref, secret_ciphertext)
               select %s, source, id, external_ref, secret_ciphertext
                 from public.financial_source_connections
                where user_id = %s and source in ('plaid', 'gmail')
                  and secret_ciphertext is not null
               on conflict (subject_hash, provider, source_ref) do update
                 set secret_ciphertext = excluded.secret_ciphertext,
                     external_ref = excluded.external_ref
               returning 1""",
            (subject, user_id),
        ).fetchall()
        if apple:
            # Apple sign-in leaves no token with Cuadrao; the revoke is owed
            # to Apple and stays pending until a revoke path exists.
            connection.execute(
                "insert into argus_private.account_deletion_revocations"
                " (subject_hash, provider, source_ref) values (%s, 'apple', %s)"
                " on conflict do nothing",
                (subject, str(uuid.uuid5(uuid.NAMESPACE_URL, f"apple:{subject}"))),
            )
        connection.execute(
            "delete from public.financial_source_connections where user_id = %s",
            (user_id,),
        )
        # 4: invite ids, through the Household-owned writer.
        household_deletion.forget_invite_party(connection, user_id=user_id)
        # 5.1: future shares in other people's plans go back to their owner.
        events += household_deletion.return_future_responsibilities(
            connection, user_id=user_id, today=now.date()
        )
        # 5.1 / 5.2: every pinned row moves to its unit's placeholder.
        used: set[str] = set()
        # Groups first, so a plan's claims are rewritten with every account
        # copy its scope made; every unit of one scope shares its placeholder.
        for (kind, unit), pid in sorted(
            units.items(), key=lambda i: (i[0][0] != "group", i[0])
        ):
            if connection.execute(
                "select argus_private.deletion_place_unit(%s, %s, %s, %s)",
                (user_id, kind, unit, pid),
            ).fetchone()[0]:
                used.add(pid)
                connection.execute(
                    "update argus_private.account_deletion_placeholders set used = true"
                    " where placeholder_id = %s",
                    (pid,),
                )
        household_deletion.write_events(connection, events)
        # 5.3, 6 and the rows outside the FKs, then the no-blocker check.
        connection.execute(
            "select argus_private.deletion_finish(%s, %s)",
            (user_id, actor_hash_for_user(user_id)),
        )
        return {
            "households_left": result.households_left,
            "households_closed": result.households_closed,
            "admin_handoffs": result.admin_handoffs,
            "plans_handed_over": result.plans_handed_over,
            "archives_passed_on": result.archives_passed_on,
            "placeholders_used": len(used),
            "credentials_captured": len(captured),
            "events": len(events),
        }

    # -- 4. the auth user --------------------------------------------------------

    def _delete_auth_user(self, user_id: str, subject: str) -> None:
        self._auth.delete_user(user_id)
        with self._households.connection() as connection:
            unused = [
                str(pid)
                for (pid,) in connection.execute(
                    "select placeholder_id from argus_private.account_deletion_placeholders"
                    " where subject_hash = %s and not used",
                    (subject,),
                ).fetchall()
            ]
        for pid in unused:
            self._auth.delete_user(pid)
        with self._households.connection() as connection, connection.transaction():
            connection.execute(
                "delete from argus_private.account_deletion_placeholders where subject_hash = %s",
                (subject,),
            )
            if unused:
                connection.execute(
                    "delete from argus_private.account_placeholders where id = any(%s::uuid[])",
                    (unused,),
                )
            connection.execute(
                "update argus_private.account_deletion_runs"
                " set status = 'auth_deleted', user_id = null, updated_at = %s"
                " where subject_hash = %s",
                (self._clock(), subject),
            )

    # -- 5. providers and analytics ---------------------------------------------

    def _settle_external(self, subject: str) -> DeletionOutcome:
        with self._households.connection() as connection:
            rows = connection.execute(
                "select provider, source_ref, external_ref, secret_ciphertext"
                " from argus_private.account_deletion_revocations"
                " where subject_hash = %s and status = 'pending' order by provider, source_ref",
                (subject,),
            ).fetchall()
            run = connection.execute(
                "select analytics_distinct_id, steps from argus_private.account_deletion_runs"
                " where subject_hash = %s",
                (subject,),
            ).fetchone()
        for provider, source_ref, external_ref, ciphertext in rows:
            if provider == "apple":
                done = self._apple.revoke(identity_id=str(source_ref))
                error = None if done else "apple_revoke_unavailable"
            elif self._revoker is None:
                done, error = False, "connector_unavailable"
            else:
                outcome = self._revoker.revoke_for_deletion(
                    source=provider,
                    connection_id=str(source_ref),
                    external_ref=external_ref or "",
                    envelope=bytes(ciphertext) if ciphertext is not None else None,
                )
                done = outcome in ("revoked", "not_applicable")
                error = None if done else "provider_revoke_failed"
            self._record_revocation(subject, provider, str(source_ref), done, error)
        steps = dict(run[1] or {})
        # Storage (3): no object store holds per-person files before #778.
        steps["storage"] = "not_applicable"
        if steps.get("analytics") not in ("deleted", "recorded_by_fake"):
            steps["analytics"] = self._analytics.delete_person(run[0])
        with self._households.connection() as connection, connection.transaction():
            pending = [
                str(p)
                for (p,) in connection.execute(
                    "select provider from argus_private.account_deletion_revocations"
                    " where subject_hash = %s and status = 'pending' order by provider",
                    (subject,),
                ).fetchall()
            ]
            if steps["analytics"] == "failed":
                pending.append("analytics")
            status: RunStatus = "auth_deleted" if pending else "done"
            connection.execute(
                "update argus_private.account_deletion_runs"
                " set status = %s, steps = %s::jsonb, updated_at = %s,"
                "     completed_at = case when %s = 'done' then %s else completed_at end"
                " where subject_hash = %s",
                (
                    status,
                    json.dumps(steps),
                    self._clock(),
                    status,
                    self._clock(),
                    subject,
                ),
            )
        if pending:
            logger.warning("Account deletion left provider work pending", pending=pending)
        return DeletionOutcome(
            status=status, pending=pending, counts=steps.get("counts", {})
        )

    def _record_revocation(
        self, subject: str, provider: str, source_ref: str, done: bool, error: str | None
    ) -> None:
        with self._households.connection() as connection, connection.transaction():
            if done:
                connection.execute(
                    "update argus_private.account_deletion_revocations"
                    " set status = 'revoked', secret_ciphertext = null, external_ref = null,"
                    "     attempts = attempts + 1, last_error = null, updated_at = now()"
                    " where subject_hash = %s and provider = %s and source_ref = %s",
                    (subject, provider, source_ref),
                )
            else:
                connection.execute(
                    "update argus_private.account_deletion_revocations"
                    " set attempts = attempts + 1, last_error = %s, updated_at = now()"
                    " where subject_hash = %s and provider = %s and source_ref = %s",
                    (error, subject, provider, source_ref),
                )


class _UnitsChanged(Exception):
    pass
