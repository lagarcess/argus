"""Owner routes for public evidence receipts: create, list, revoke.

Every route here is behind the default-off sharing flag and answers 404 while it
is off, so the endpoints do not exist for a client until the founder turns them
on.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from loguru import logger

from argus.api.dependencies import current_user, problem, require_account_capability
from argus.api.guest_access import client_identity
from argus.api.pagination import decode_cursor, encode_cursor, invalid_cursor_problem
from argus.api.public_excerpt_schemas import (
    PublicExcerptCreate,
    PublicExcerptCreateResponse,
    PublicExcerptListResponse,
    PublicExcerptRevokeResponse,
)
from argus.api.public_excerpts import (
    RECEIPT_CREATE_DAILY_LIMIT,
    RECEIPT_CREATE_DAILY_WINDOW_SECONDS,
    RECEIPT_CREATE_LIMIT,
    RECEIPT_CREATE_WINDOW_SECONDS,
    EvidenceReceiptSourceMissingError,
    create_receipt_for_artifact,
    public_excerpt_repository,
    require_evidence_receipt_sharing_enabled,
)
from argus.api.rate_limits import SlidingWindowLimiter
from argus.api.schemas import User
from argus.domain.public_excerpts import (
    PublicExcerptOwnerNoteError,
    PublicExcerptSanitizationError,
    PublicExcerptSourceError,
    normalize_owner_note,
    snapshot_list_item,
)
from argus.domain.supabase_public_excerpts import (
    DEFAULT_OWNER_PAGE_SIZE,
    MAX_OWNER_PAGE_SIZE,
)
from argus.observability.product_events import capture_product_event

router = APIRouter(prefix="/api/v1", tags=["evidence-receipts"])

_RECEIPT_CREATE_LIMITER = SlidingWindowLimiter()


def reset_receipt_create_limiter_for_tests() -> None:
    _RECEIPT_CREATE_LIMITER.reset()


def _enforce_create_rate_limit(request: Request, *, user: User) -> None:
    """Rate-limit receipt creation, honouring the documented admin bypass.

    `docs/API_CONTRACT.md` says backend quota and rate-limit restrictions are
    bypassed for `profiles.is_admin`, and the mock developer account is an admin, so
    an unconditional limiter also blocked internal QA of this surface. The limit
    still applies to every ordinary account, which is who section 7.4 is about.
    """
    if user.is_admin:
        return
    visitor = client_identity(request)
    for limit, window in (
        (RECEIPT_CREATE_LIMIT, RECEIPT_CREATE_WINDOW_SECONDS),
        (RECEIPT_CREATE_DAILY_LIMIT, RECEIPT_CREATE_DAILY_WINDOW_SECONDS),
    ):
        retry_after = _RECEIPT_CREATE_LIMITER.record_or_retry_after(
            keys=(
                f"receipt-create:user:{user.id}:{window}",
                f"receipt-create:visitor:{visitor}:{window}",
            ),
            limit=limit,
            window_seconds=window,
        )
        if retry_after is None:
            continue
        raise problem(
            request,
            status_code=429,
            code="too_many_requests",
            title="Too Many Requests",
            detail="You have created a lot of links recently. Try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )


@router.post(
    "/evidence-artifacts/{artifact_id}/public-excerpt",
    response_model=PublicExcerptCreateResponse,
)
def create_public_excerpt(
    artifact_id: str,
    payload: PublicExcerptCreate,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> PublicExcerptCreateResponse:
    require_evidence_receipt_sharing_enabled()
    require_account_capability(
        request,
        "can_save_decision",
        detail="Sign in to share a result.",
        reason="share_result",
    )
    try:
        owner_note = normalize_owner_note(payload.owner_note)
    except PublicExcerptOwnerNoteError as exc:
        raise problem(
            request,
            status_code=422,
            code="receipt_note_rejected",
            title="Note Rejected",
            detail=str(exc),
        ) from exc
    _enforce_create_rate_limit(request, user=user)
    try:
        snapshot, created = create_receipt_for_artifact(
            user=user,
            artifact_id=artifact_id,
            owner_note=owner_note,
        )
    except EvidenceReceiptSourceMissingError as exc:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="That result is not available.",
        ) from exc
    except PublicExcerptSourceError as exc:
        raise problem(
            request,
            status_code=422,
            code="receipt_source_unsupported",
            title="Not Shareable",
            detail=str(exc),
        ) from exc
    except PublicExcerptSanitizationError as exc:
        # Fail closed. A payload that cannot be proven clean is never published.
        logger.error("Receipt payload failed the never-expose audit", error=str(exc))
        raise problem(
            request,
            status_code=500,
            code="receipt_sanitization_failed",
            title="Could Not Share",
            detail="Argus could not safely build that link. Please try again later.",
        ) from exc
    if created:
        # Only a real insert counts. Sharing the same result again returns the
        # existing link, and counting that would inflate the funnel's creation
        # stage with retries and reloads.
        capture_product_event(
            "receipt_created",
            user_id=user.id,
            status="created",
            attributes={"receipt_digest": snapshot.payload_digest[:16]},
        )
    return PublicExcerptCreateResponse(receipt=snapshot_list_item(snapshot))


@router.get("/public-excerpts", response_model=PublicExcerptListResponse)
def list_public_excerpts(
    request: Request,
    limit: int = Query(default=DEFAULT_OWNER_PAGE_SIZE, ge=1, le=MAX_OWNER_PAGE_SIZE),
    cursor: str | None = None,
    user: User = Depends(current_user),  # noqa: B008
) -> PublicExcerptListResponse:
    """The owner's receipts, newest first, paginated.

    Paginated rather than capped: Data Controls is the only place an owner can find
    a snapshot id to revoke, so a row hidden behind a cap would be a public page
    they cannot take down.
    """
    require_evidence_receipt_sharing_enabled()
    require_account_capability(
        request,
        "can_save_decision",
        detail="Sign in to review shared links.",
        reason="share_result",
    )
    before: tuple[str, str] | None = None
    if cursor:
        raw_created_at, cursor_id = decode_cursor(cursor, request)
        try:
            datetime.fromisoformat(raw_created_at)
        except ValueError:
            raise invalid_cursor_problem(request) from None
        if not cursor_id:
            raise invalid_cursor_problem(request)
        before = (raw_created_at, cursor_id)

    # One extra row answers "is there another page" without a second query.
    page = public_excerpt_repository().list_public_excerpt_snapshots(
        owner_id=user.id,
        limit=limit + 1,
        before=before,
    )
    has_more = len(page) > limit
    snapshots = page[:limit]
    next_cursor = (
        encode_cursor(snapshots[-1].created_at.isoformat(), snapshots[-1].id)
        if has_more and snapshots
        else None
    )
    return PublicExcerptListResponse(
        items=[snapshot_list_item(snapshot) for snapshot in snapshots],
        next_cursor=next_cursor,
    )


@router.delete(
    "/public-excerpts/{snapshot_id}",
    response_model=PublicExcerptRevokeResponse,
)
def revoke_public_excerpt(
    snapshot_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> PublicExcerptRevokeResponse:
    require_evidence_receipt_sharing_enabled()
    require_account_capability(
        request,
        "can_save_decision",
        detail="Sign in to manage shared links.",
        reason="share_result",
    )
    snapshot, revoked_now = public_excerpt_repository().revoke_public_excerpt_snapshot(
        owner_id=user.id,
        snapshot_id=snapshot_id,
    )
    if snapshot is None:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="That link is not available.",
        )
    if revoked_now:
        # Only the transition is a revocation. A network retry asks for the same
        # outcome and gets it, but counting it again would overstate revocations in
        # append-only evidence.
        capture_product_event("receipt_revoked", user_id=user.id, status="revoked")
    return PublicExcerptRevokeResponse(receipt=snapshot_list_item(snapshot))
