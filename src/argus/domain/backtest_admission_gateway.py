"""Supabase-backed #230 admission calls, kept out of the gateway mega-file.

These functions take the PostgREST client owned by ``SupabaseGateway`` and call
the database-owned admission operation added by
``supabase/migrations/20260718000001_atomic_backtest_admission.sql``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from argus.domain.backtest_admission import admission_limits


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_one(result: Any) -> Any:
    data = getattr(result, "data", None)
    if isinstance(data, list):
        return data[0] if data else None
    return data


def admit_backtest_job(
    client: Any,
    *,
    user_id: str,
    operation_scope: str,
    idempotency_key: str,
    identity_hash: str,
    payload_hash: str,
    launch_payload: dict[str, Any],
    initial_status: str,
    conversation_id: str | None = None,
    request_message_id: str | None = None,
    confirmation_message_id: str | None = None,
    execution_metadata: dict[str, Any] | None = None,
    simulation_day_limit: int = 50,
) -> dict[str, Any]:
    """One database-owned admission: replay/collision, allowance, per-user
    then global capacity, then insert plus allowance charge (#230)."""

    limits = admission_limits()
    result = client.rpc(
        "admit_backtest_job",
        {
            "p_user_id": user_id,
            "p_operation_scope": operation_scope,
            "p_idempotency_key": idempotency_key,
            "p_identity_hash": identity_hash,
            "p_payload_hash": payload_hash,
            "p_launch_payload": launch_payload,
            "p_initial_status": initial_status,
            "p_conversation_id": conversation_id,
            "p_request_message_id": request_message_id,
            "p_confirmation_message_id": confirmation_message_id,
            "p_execution_metadata": execution_metadata or {},
            "p_user_running_limit": limits.user_running,
            "p_user_queued_limit": limits.user_queued,
            "p_global_running_limit": limits.global_running,
            "p_global_queued_limit": limits.global_queued,
            "p_simulation_day_limit": simulation_day_limit,
        },
    ).execute()
    row = result.data if isinstance(result.data, dict) else _row_one(result)
    if not isinstance(row, dict) or "decision" not in row:
        raise RuntimeError("Backtest admission did not return a decision.")
    return row


def get_backtest_job_by_reservation(
    client: Any,
    *,
    user_id: str,
    operation_scope: str,
    idempotency_key: str,
) -> dict[str, Any] | None:
    result = (
        client.table("backtest_jobs")
        .select("*")
        .eq("user_id", user_id)
        .eq("operation_scope", operation_scope)
        .eq("idempotency_key", idempotency_key)
        .limit(1)
        .execute()
    )
    row = _row_one(result)
    return dict(row) if row is not None else None


def get_message_row(
    client: Any,
    *,
    message_id: str,
) -> dict[str, Any] | None:
    result = (
        client.table("messages")
        .select("*")
        .eq("id", message_id)
        .limit(1)
        .execute()
    )
    row = _row_one(result)
    return dict(row) if row is not None else None


def claim_running_direct_job(
    client: Any,
    *,
    user_id: str,
    job_id: str,
) -> dict[str, Any] | None:
    """Row-locking conditional claim: returns the job only while it is still
    ``running``, serializing with the stale reconciler before the finalizer
    creates the Run/evidence tuple."""

    claimed = (
        client.table("backtest_jobs")
        .update({"updated_at": _now_iso()})
        .eq("user_id", user_id)
        .eq("id", job_id)
        .eq("status", "running")
        .execute()
    )
    row = _row_one(claimed)
    return dict(row) if row is not None else None


def finalize_direct_backtest_job(
    client: Any,
    *,
    user_id: str,
    job_id: str,
    status: str,
    result_run_id: str | None = None,
    failure_code: str | None = None,
    failure_detail: str | None = None,
    retryable: bool = False,
    execution_metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {
        "status": status,
        "result_run_id": result_run_id,
        "failure_code": failure_code,
        "failure_detail": failure_detail,
        "retryable": retryable,
        "finished_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    if execution_metadata is not None:
        payload["execution_metadata"] = execution_metadata
    updated = (
        client.table("backtest_jobs")
        .update(payload)
        .eq("user_id", user_id)
        .eq("id", job_id)
        # Reconciler and finalizer serialize on the same row; a terminal
        # reconciliation decision is final and late success cannot supersede.
        .in_("status", ["queued", "running"])
        .execute()
    )
    row = _row_one(updated)
    return dict(row) if row is not None else None
