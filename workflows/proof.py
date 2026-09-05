from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from argus.domain.backtest_job_scopes import PROOF_OPERATION_SCOPE

PROOF_KIND = "render_workflow_proof"
# A proof job is not conversation work: it carries its own operation scope
# and no conversation, so no activity reader can ever project it. The
# migration 20260905000000_workflow_proof_jobs_leave_conversations.sql
# reclassifies rows the seeder wrote under the column default by this
# created_by signature.
PROOF_SEED_CREATED_BY = "workflows.proof_cli"
PROOF_EMAIL_DOMAIN = "example.invalid"
WORKFLOW_DATABASE_URL_ENV = "ARGUS_WORKFLOW_DATABASE_URL"
LEGACY_DATABASE_URL_ENV = "DATABASE_URL"
PROVIDER_MODE_ENV = "ARGUS_MARKET_DATA_PROVIDER_MODE"
CACHE_ENABLED_ENV = "ENABLE_MARKET_DATA_CACHE"
DEFAULT_PROOF_USER_ID = "00000000-0000-4000-8000-000000000124"
PROOF_USER_ID_ENV = "ARGUS_WORKFLOW_PROOF_USER_ID"


class WorkflowProofError(RuntimeError):
    """Raised when a proof job cannot be executed safely."""


class ProofJobGateway(Protocol):
    def fetch_job(self, job_id: str) -> dict[str, Any] | None:
        """Return one backtest job row by id."""

    def update_job_status(
        self,
        *,
        job_id: str,
        status: str,
        execution_metadata: dict[str, Any],
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> dict[str, Any]:
        """Persist a job status transition and return the updated row."""


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_database_url(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    database_url = (
        source.get(WORKFLOW_DATABASE_URL_ENV) or source.get(LEGACY_DATABASE_URL_ENV) or ""
    ).strip()
    if not database_url:
        raise RuntimeError(
            f"{WORKFLOW_DATABASE_URL_ENV} is required for Render Workflow proof jobs. "
            f"Configure it as a Render secret. {LEGACY_DATABASE_URL_ENV} is still "
            "accepted as a local/backward-compatible fallback."
        )
    return database_url


def workflow_runtime_facts(env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = os.environ if env is None else env
    provider_mode = source.get(PROVIDER_MODE_ENV, "").strip()
    market_data_cache = source.get(CACHE_ENABLED_ENV, "").strip()
    return {
        "provider_mode": provider_mode or "<missing>",
        "market_data_cache": market_data_cache or "<missing>",
    }


def stable_payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def proof_user_email(user_id: str) -> str:
    return f"render-workflow-proof+{user_id}@{PROOF_EMAIL_DOMAIN}"


def _proof_uuid(value: str, *, label: str) -> str:
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise WorkflowProofError(f"{label} must be a valid UUID.") from exc


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def _job_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("execution_metadata") or {}
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def _launch_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("launch_payload") or {}
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def _assert_proof_job(row: Mapping[str, Any]) -> None:
    if row.get("status") != "queued":
        raise WorkflowProofError(
            f"Workflow proof expected queued job, found {row.get('status')!r}."
        )
    payload = _launch_payload(row)
    if payload.get("kind") != PROOF_KIND:
        raise WorkflowProofError(
            "Workflow proof can only execute launch_payload.kind=" f"{PROOF_KIND!r} jobs."
        )


def run_workflow_proof(
    gateway: ProofJobGateway,
    *,
    job_id: str,
    nonce: str,
    workflow_run_id: str | None = None,
    runtime_facts: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    row = gateway.fetch_job(job_id)
    if row is None:
        raise WorkflowProofError(f"Backtest job {job_id} was not found.")
    _assert_proof_job(row)

    started_at = utcnow_iso()
    metadata = _job_metadata(row)
    metadata["workflow_proof"] = {
        "kind": PROOF_KIND,
        "nonce": nonce,
        "workflow_run_id": workflow_run_id,
        "runtime_facts": dict(runtime_facts or workflow_runtime_facts()),
        "started_at": started_at,
    }
    running = gateway.update_job_status(
        job_id=job_id,
        status="running",
        execution_metadata=metadata,
        started_at=started_at,
    )
    if str(running.get("status") or "") != "running":
        # The transition was refused: another finalizer already owns the
        # job's terminal state, and the proof reports it rather than
        # overwriting it.
        return _proof_result(running, job_id=job_id, nonce=nonce, workflow_run_id=workflow_run_id)

    finished_at = utcnow_iso()
    completed_metadata = _job_metadata(running)
    workflow_metadata = dict(completed_metadata.get("workflow_proof") or {})
    workflow_metadata["finished_at"] = finished_at
    completed_metadata["workflow_proof"] = workflow_metadata
    succeeded = gateway.update_job_status(
        job_id=job_id,
        status="succeeded",
        execution_metadata=completed_metadata,
        finished_at=finished_at,
    )
    readback = gateway.fetch_job(job_id) or succeeded
    return _proof_result(readback, job_id=job_id, nonce=nonce, workflow_run_id=workflow_run_id)


def _proof_result(
    row: Mapping[str, Any],
    *,
    job_id: str,
    nonce: str,
    workflow_run_id: str | None,
) -> dict[str, Any]:
    return {
        "job_id": str(row.get("id") or job_id),
        "status": row.get("status"),
        "nonce": nonce,
        "workflow_run_id": workflow_run_id,
        "runtime_facts": _json_safe(
            (row.get("execution_metadata") or {})
            .get("workflow_proof", {})
            .get("runtime_facts", {})
        ),
        "execution_metadata": _json_safe(row.get("execution_metadata") or {}),
    }


class PostgresProofJobGateway:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @classmethod
    def from_env(cls) -> PostgresProofJobGateway:
        return cls(require_database_url())

    def _connect(self) -> Any:
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(self.database_url, row_factory=dict_row)

    def fetch_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select *
                    from public.backtest_jobs
                    where id = %s
                    limit 1
                    """,
                    (job_id,),
                )
                row = cur.fetchone()
        return _json_safe(row) if row else None

    def update_job_status(
        self,
        *,
        job_id: str,
        status: str,
        execution_metadata: dict[str, Any],
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> dict[str, Any]:
        from argus.domain.backtest_job_lifecycle import (
            job_success_write_sql_predicate,
        )
        from psycopg.types.json import Jsonb

        # The proof's running and succeeded transitions are success-lifecycle
        # movements, valid only while the job may still succeed. The predicate
        # is generated beside the card-restore classification, so a state the
        # card was restored from can never be converted back into a live or
        # successful job by the proof machinery. A refused write returns the
        # standing row and the proof reports it instead of overwriting it.
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    update public.backtest_jobs
                    set status = %(status)s,
                        started_at = coalesce(started_at, %(started_at)s),
                        finished_at = coalesce(%(finished_at)s, finished_at),
                        attempts = attempts + case
                          when %(status)s = 'running' then 1
                          else 0
                        end,
                        execution_metadata = %(execution_metadata)s,
                        updated_at = %(updated_at)s
                    where id = %(job_id)s
                      and {job_success_write_sql_predicate()}
                    returning *
                    """,
                    {
                        "job_id": job_id,
                        "status": status,
                        "started_at": started_at,
                        "finished_at": finished_at,
                        "execution_metadata": Jsonb(execution_metadata),
                        "updated_at": utcnow_iso(),
                    },
                )
                row = cur.fetchone()
                if row is None:
                    standing = self.fetch_job(job_id)
                    if standing is None:
                        raise WorkflowProofError(f"Backtest job {job_id} was not found.")
                    print(  # noqa: T201 - workflow task output surface
                        json.dumps(
                            {
                                "event": "proof_status_write_refused",
                                "job_id": job_id,
                                "requested_status": status,
                                "standing_status": str(standing.get("status") or ""),
                            }
                        ),
                        file=sys.stderr,
                    )
                    return standing
        return _json_safe(row)

    def ensure_proof_profile(self, *, user_id: str, email: str) -> None:
        from psycopg.types.json import Jsonb

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into auth.users (
                      id,
                      aud,
                      role,
                      email,
                      email_confirmed_at,
                      raw_app_meta_data,
                      raw_user_meta_data,
                      created_at,
                      updated_at,
                      is_anonymous
                    )
                    values (
                      %(user_id)s,
                      'authenticated',
                      'authenticated',
                      %(email)s,
                      now(),
                      %(app_metadata)s,
                      '{}'::jsonb,
                      now(),
                      now(),
                      false
                    )
                    on conflict (id) do nothing
                    """,
                    {
                        "user_id": user_id,
                        "email": email,
                        "app_metadata": Jsonb(
                            {"provider": "email", "providers": ["email"]}
                        ),
                    },
                )
                cur.execute(
                    """
                    insert into public.profiles (
                      id,
                      email,
                      display_name,
                      language,
                      locale,
                      theme
                    )
                    values (
                      %(user_id)s,
                      %(email)s,
                      'Render Workflow Proof',
                      'en',
                      'en-US',
                      'dark'
                    )
                    on conflict (id) do nothing
                    """,
                    {
                        "user_id": user_id,
                        "email": email,
                    },
                )

    def create_proof_job(
        self,
        *,
        user_id: str,
        nonce: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        payload: dict[str, Any] = {
            "kind": PROOF_KIND,
            "nonce": nonce,
            "created_by": PROOF_SEED_CREATED_BY,
        }
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.backtest_jobs (
                      user_id,
                      operation_scope,
                      idempotency_key,
                      payload_hash,
                      launch_payload,
                      status,
                      execution_metadata
                    )
                    values (%s, %s, %s, %s, %s, 'queued', '{}'::jsonb)
                    returning *
                    """,
                    (
                        user_id,
                        PROOF_OPERATION_SCOPE,
                        idempotency_key,
                        stable_payload_hash(payload),
                        Jsonb(payload),
                    ),
                )
                row = cur.fetchone()
        return _json_safe(row)


def _dump_json(payload: Mapping[str, Any]) -> None:
    json.dump(payload, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


def _seed(args: argparse.Namespace) -> int:
    gateway = PostgresProofJobGateway.from_env()
    user_id = _proof_uuid(
        args.user_id or os.getenv(PROOF_USER_ID_ENV) or DEFAULT_PROOF_USER_ID,
        label="proof user id",
    )
    email = proof_user_email(user_id)
    gateway.ensure_proof_profile(user_id=user_id, email=email)
    row = gateway.create_proof_job(
        user_id=user_id,
        nonce=args.nonce,
        idempotency_key=args.idempotency_key,
    )
    _dump_json(
        {
            "job_id": row["id"],
            "user_id": user_id,
            "email": email,
            "operation_scope": row["operation_scope"],
            "nonce": args.nonce,
            "status": row["status"],
        }
    )
    return 0


def _direct(args: argparse.Namespace) -> int:
    result = run_workflow_proof(
        PostgresProofJobGateway.from_env(),
        job_id=args.job_id,
        nonce=args.nonce,
        workflow_run_id="direct-local-debug",
    )
    _dump_json(result)
    return 0


def _verify(args: argparse.Namespace) -> int:
    row = PostgresProofJobGateway.from_env().fetch_job(args.job_id)
    if row is None:
        raise WorkflowProofError(f"Backtest job {args.job_id} was not found.")
    metadata = row.get("execution_metadata") or {}
    workflow_metadata = (
        metadata.get("workflow_proof") if isinstance(metadata, dict) else None
    )
    if args.expect_nonce or args.expect_provider_mode:
        if row.get("status") != "succeeded":
            raise WorkflowProofError(
                "Workflow proof expected succeeded job, "
                f"found {row.get('status')!r}."
            )
        if not isinstance(workflow_metadata, dict):
            raise WorkflowProofError("Workflow proof metadata is missing.")
        if workflow_metadata.get("kind") != PROOF_KIND:
            raise WorkflowProofError(
                "Workflow proof metadata expected "
                f"kind={PROOF_KIND!r}, found {workflow_metadata.get('kind')!r}."
            )
        if not row.get("finished_at") or not workflow_metadata.get("finished_at"):
            raise WorkflowProofError("Workflow proof expected finished_at timestamps.")
        if args.expect_nonce:
            actual_nonce = str(workflow_metadata.get("nonce") or "").strip()
            if actual_nonce != args.expect_nonce:
                raise WorkflowProofError(
                    "Workflow proof expected nonce "
                    f"{args.expect_nonce!r}, found {actual_nonce or '<missing>'!r}."
                )
    runtime_facts = (
        workflow_metadata.get("runtime_facts")
        if isinstance(workflow_metadata, dict)
        else None
    )
    if args.expect_provider_mode:
        actual_provider_mode = ""
        if isinstance(runtime_facts, dict):
            actual_provider_mode = str(runtime_facts.get("provider_mode") or "").strip()
        if actual_provider_mode != args.expect_provider_mode:
            raise WorkflowProofError(
                "Workflow proof expected "
                f"{PROVIDER_MODE_ENV}={args.expect_provider_mode!r}, "
                f"found {actual_provider_mode or '<missing>'!r}."
            )
    _dump_json(
        {
            "job_id": row["id"],
            "status": row["status"],
            "execution_metadata": row.get("execution_metadata") or {},
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed or verify Render proof jobs.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    seed = subcommands.add_parser("seed")
    seed.add_argument("--user-id")
    seed.add_argument("--nonce")
    seed.add_argument("--idempotency-key")
    seed.set_defaults(func=_seed)

    direct = subcommands.add_parser("direct")
    direct.add_argument("--job-id", required=True)
    direct.add_argument("--nonce", required=True)
    direct.set_defaults(func=_direct)

    verify = subcommands.add_parser("verify")
    verify.add_argument("--job-id", required=True)
    verify.add_argument("--expect-nonce")
    verify.add_argument("--expect-provider-mode")
    verify.set_defaults(func=_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "nonce") and not args.nonce:
        args.nonce = str(uuid4())
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
