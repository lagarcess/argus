"""PostgREST reads that tell a person's Personal records from a Business space's."""

from __future__ import annotations

from typing import Any, Literal

from postgrest import CountMethod

from supabase import Client

SourceArtifactTable = Literal[
    "evidence_artifacts", "ideas", "idea_versions", "decision_notes"
]


class SupabaseSpaceReadMixin:
    client: Client

    def count_completed_runs(self, *, user_id: str) -> int:
        """Completed runs outside Business chats; a run with no chat is Personal."""

        def completed(select: str) -> Any:
            return (
                self.client.table("backtest_runs")
                .select(select, count=CountMethod.exact)
                .eq("user_id", user_id)
                .eq("status", "completed")
            )

        in_business = completed("id, conversations!inner(owner_space_id)").not_.is_(
            "conversations.owner_space_id", "null"
        )
        total = completed("id").execute().count or 0
        return int(total) - int(in_business.execute().count or 0)

    def artifact_source_conversation_id(
        self, *, table: SourceArtifactTable, user_id: str, artifact_id: str
    ) -> str | None:
        """The conversation the person's saved artifact came from, or None."""
        rows: list[dict[str, Any]] = (
            self.client.table(table)
            .select("source_conversation_id")
            .eq("user_id", user_id)
            .eq("id", artifact_id)
            .limit(1)
            .execute()
        ).data or []  # type: ignore[assignment]
        source = rows[0].get("source_conversation_id") if rows else None
        return str(source) if source else None
