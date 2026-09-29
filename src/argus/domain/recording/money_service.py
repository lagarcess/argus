"""Personal money orchestration over the shared atomic repository."""

from typing import Any
from uuid import UUID

from argus.domain.recording.errors import (
    AccountNotFound,
    RecordingInputError,
    StaleVersion,
)
from argus.domain.recording.money_plan import MoneyPlan, plan, request_identity
from argus.domain.recording.money_reads import (
    activity,
    current_activities,
    groups,
    render_activity,
)
from argus.domain.recording.money_schemas import MoneyRequest
from argus.domain.recording.repository import StoredAccount
from argus.domain.recording.schemas import account_response
from argus.domain.recording.service import FinancialAccountService


class MoneyService:
    def __init__(self, accounts: FinancialAccountService) -> None:
        self.accounts = accounts
        self.repository = accounts._repository

    def preview(
        self, *, user_id: str, request: MoneyRequest, activity_id: str | None = None
    ) -> dict[str, Any]:
        activity_id = self._id(activity_id)
        return plan(
            self.accounts.list_accounts(user_id=user_id),
            request,
            activity_id,
            self.accounts._clock(),
        ).preview

    def write(
        self,
        *,
        user_id: str,
        request: MoneyRequest,
        idempotency_key: str,
        activity_id: str | None = None,
    ) -> dict[str, Any]:
        from argus.domain.recording.money_storage import transact

        activity_id = self._id(activity_id)

        def planner(accounts: list[StoredAccount]) -> MoneyPlan:
            result = plan(accounts, request, activity_id, self.accounts._clock())
            if request.expected_versions != result.preview["expected_versions"]:
                raise StaleVersion()
            if not result.preview["ready"]:
                raise RecordingInputError(
                    "balance_coverage_required", "Review each balance question."
                )
            if request.preview_token != result.preview["preview_token"]:
                raise RecordingInputError(
                    "preview_required", "Review the proposed change before saving it."
                )
            return result

        records, aid, revision, affected, replayed = transact(
            self.repository,
            user_id,
            idempotency_key,
            request_identity(request, activity_id),
            planner,
            self.accounts._clock(),
        )
        return {
            "activity": activity(records, aid, revision),
            "accounts": [
                account_response(s) for s in records if s.account.id in affected
            ],
            "replayed": replayed,
        }

    def detail(self, *, user_id: str, activity_id: str) -> dict[str, Any]:
        aid = self._id(activity_id)
        assert aid is not None
        return activity(self.accounts.list_accounts(user_id=user_id), aid)

    def history(self, *, user_id: str, activity_id: str) -> dict[str, Any]:
        records = self.accounts.list_accounts(user_id=user_id)
        aid = self._id(activity_id)
        assert aid is not None
        revisions = groups(records).get(aid)
        if not revisions:
            raise AccountNotFound()
        return {
            "items": [
                render_activity(aid, revisions, r)
                for r in sorted(revisions, reverse=True)
            ],
            "next_cursor": None,
        }

    def purchases(self, *, user_id: str, currency: str | None = None) -> dict[str, Any]:
        records = current_activities(self.accounts.list_accounts(user_id=user_id))
        refunded: dict[str, int] = {}
        for item in records:
            purchase_id = item["purchase_activity_id"]
            if purchase_id:
                refunded[purchase_id] = (
                    refunded.get(purchase_id, 0) + item["amount_minor"]
                )
        items = []
        for item in records:
            if item["kind"] != "expense" or currency and item["currency"] != currency:
                continue
            total = refunded.get(item["activity_id"], 0)
            items.append(
                {
                    **item,
                    "refunded_minor": total,
                    "refundable_minor": item["amount_minor"] - total,
                }
            )
        return {"items": sorted(items, key=lambda a: a["occurred_at"], reverse=True)}

    @staticmethod
    def _id(value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(UUID(value))
        except ValueError:
            raise AccountNotFound() from None
