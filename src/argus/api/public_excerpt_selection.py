"""Owner selection boundary; candidates, preview and publish use one projection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from argus.api import state as api_state
from argus.api.public_excerpt_schemas import (
    PUBLIC_EXCERPT_MAX_TURNS,
    PublicExcerptCandidate,
    PublicExcerptCandidates,
    PublicExcerptPreview,
    PublicExcerptSnapshot,
    PublicExcerptToolSource,
    PublicExcerptTurnsPayload,
)
from argus.api.schemas import Message, User
from argus.domain.job_settlement import RESEARCH_OPERATION_SCOPE
from argus.domain.public_excerpt_kinds import document_kind
from argus.domain.public_excerpt_tool_turns import project_tool_turn
from argus.domain.public_excerpt_turns import (
    audit_text,
    project_backtest_turn,
    project_research_turn,
    refuse,
)
from argus.domain.public_excerpts import (
    PublicExcerptSourceError,
    new_public_excerpt_id,
    payload_digest,
    snapshot_list_item,
)


@dataclass
class SelectionContext:
    user: User
    conversation: Any
    messages: list[Message]
    jobs: list[dict[str, Any]]
    artifacts: list[Any]


def _context(user: User, conversation_id: str) -> SelectionContext:
    from argus.api.guest_access import current_account_context
    from argus.api.public_excerpts import (
        EvidenceReceiptSourceMissingError,
        _owned_source_conversation,
    )

    account = current_account_context()
    if (
        account is not None
        and account.user_id == user.id
        and not account.capabilities.can_save_decision
    ):
        refuse("unsupported_turn")
    conversation = _owned_source_conversation(
        user_id=user.id, conversation_id=conversation_id
    )
    if conversation is None or conversation.deleted_at is not None:
        raise EvidenceReceiptSourceMissingError("That conversation is not available.")
    gateway = api_state.supabase_gateway
    if gateway is not None:
        messages = gateway.list_messages(
            user_id=user.id, conversation_id=conversation_id, limit=None
        )
        jobs, artifacts = gateway.public_excerpt_source_records(
            owner_id=user.id, conversation_id=conversation_id
        )
    else:
        messages = list(api_state.store.messages.get(conversation_id, []))
        jobs = [
            job
            for job in api_state.store.backtest_jobs.values()
            if job.get("user_id") == user.id
            and job.get("conversation_id") == conversation_id
        ]
        artifacts = [
            artifact
            for artifact in api_state.store.evidence_artifacts.values()
            if artifact.source_conversation_id == conversation_id
            and api_state.store.evidence_artifact_owners.get(artifact.id) == user.id
        ]
    return SelectionContext(
        user,
        conversation,
        sorted(messages, key=lambda m: (m.created_at, m.id)),
        jobs,
        artifacts,
    )


def _run_id(message: Message) -> str | None:
    metadata = message.metadata or {}
    candidate = metadata.get("result_run_id") or metadata.get("latest_run_id")
    bank = metadata.get("result_fact_bank")
    return candidate or (bank.get("run_id") if isinstance(bank, dict) else None)


def _jobs(context: SelectionContext, message: Message) -> list[dict[str, Any]]:
    metadata = message.metadata or {}
    job_ids = set()
    if metadata.get("backtest_job_id"):
        job_ids.add(metadata["backtest_job_id"])
    if isinstance(metadata.get("backtest_job"), dict):
        job_ids.add(metadata["backtest_job"].get("id"))
    for item in metadata.get("tool_jobs", []):
        if not isinstance(item, dict) or not isinstance(item.get("job"), dict):
            refuse("not_completed")
        job_ids.add(item["job"].get("id"))
    jobs = [
        job
        for job in context.jobs
        if job.get("id") in job_ids
        or (job.get("execution_metadata") or {}).get("research_result_message_id")
        == message.id
    ]
    if job_ids - {job.get("id") for job in jobs}:
        refuse("not_completed")
    return jobs


def _job(context: SelectionContext, message: Message) -> dict[str, Any] | None:
    jobs = _jobs(context, message)
    requests = {job.get("request_message_id") for job in jobs}
    if len(requests) > 1:
        refuse("unsupported_turn")
    return jobs[0] if jobs else None


def _question(
    context: SelectionContext, message: Message, job: dict[str, Any] | None
) -> Message | None:
    if job:
        return next(
            (
                m
                for m in context.messages
                if m.id == job.get("request_message_id") and m.role == "user"
            ),
            None,
        )
    index = context.messages.index(message)
    return next((m for m in reversed(context.messages[:index]) if m.role == "user"), None)


def _project(
    context: SelectionContext, message: Message, owner_note: str | None
) -> tuple[Any, list[Any], list[str], list[PublicExcerptToolSource]]:
    from argus.api.public_excerpts import _owned_run

    metadata = message.metadata or {}
    if (
        message.role != "assistant"
        or any(
            key in metadata
            for key in ("confirmation", "confirmation_card", "clarification")
        )
        or metadata.get("conversation_mode") in {"confirmation", "clarification"}
    ):
        refuse("unsupported_turn")
    if metadata.get("memory_recalls"):
        refuse("memory_used")
    jobs = _jobs(context, message)
    job = _job(context, message)
    terminal = metadata.get("agent_runtime_turn")
    terminal = terminal if isinstance(terminal, dict) else {}
    if job is None and (metadata.get("backtest_job_id") or metadata.get("backtest_job")):
        refuse("not_completed")
    for observed_job in jobs:
        from argus.api.conversation_activity import _memory_result_hydrateable

        job_run = _owned_run(
            user_id=context.user.id, run_id=observed_job.get("result_run_id")
        )
        observed = SimpleNamespace(
            backtest_runs={job_run.id: job_run} if job_run is not None else {},
            backtest_run_owners={job_run.id: context.user.id}
            if job_run is not None
            else {},
            evidence_artifacts={a.id: a for a in context.artifacts},
            evidence_artifact_owners={a.id: context.user.id for a in context.artifacts},
            conversation_owners={context.conversation.id: context.user.id},
            messages={context.conversation.id: context.messages},
        )
        if not _memory_result_hydrateable(
            observed,
            user_id=context.user.id,
            conversation_id=context.conversation.id,
            job=observed_job,
        ):
            refuse("not_completed")
    if not jobs and not (
        terminal.get("terminal") is True and terminal.get("status") == "completed"
    ):
        refuse("not_completed")
    request = _question(context, message, job)
    if request is None:
        refuse("missing_question", "question")
    private_ids = tuple(
        [
            context.user.id,
            context.conversation.id,
            *(m.id for m in context.messages),
            *(str(j["id"]) for j in context.jobs),
            *(a.id for a in context.artifacts),
        ]
    )
    audit_text(request.content, field="question", private_ids=private_ids)
    audit_text(owner_note, field="owner_note", private_ids=private_ids)
    language = context.conversation.language
    if "tool_result_cards" in metadata:
        return _project_tool_message(
            context, message, request.content, owner_note, private_ids, jobs
        )
    audit_text(message.content, field="answer", private_ids=private_ids)
    if "research" in metadata:
        if job is not None and job.get("operation_scope") != RESEARCH_OPERATION_SCOPE:
            refuse("unsupported_turn")
        return (
            project_research_turn(
                message=message,
                question=request.content,
                owner_note=owner_note,
                language=language,
                private_ids=private_ids,
            ),
            [],
            [],
            [],
        )
    run_id = job.get("result_run_id") if job is not None else _run_id(message)
    if not run_id:
        refuse("unsupported_turn")
    run = _owned_run(user_id=context.user.id, run_id=run_id)
    if run is None or run.conversation_id != context.conversation.id:
        refuse("unsupported_backtest")
    artifact = next(
        (
            a
            for a in context.artifacts
            if a.source_run_id == run_id and a.artifact_type == "backtest"
        ),
        None,
    )
    if artifact is None:
        refuse("unsupported_backtest")
    leaf = project_backtest_turn(
        run=run,
        title=artifact.title,
        owner_note=owner_note,
        language=language,
        private_ids=(*private_ids, run_id),
    )
    return leaf, [artifact], [run_id], []


def _project_tool_message(
    context: SelectionContext,
    message: Message,
    question: str,
    owner_note: str | None,
    private_ids: tuple[str, ...],
    jobs: list[dict[str, Any]],
) -> tuple[Any, list[Any], list[str], list[PublicExcerptToolSource]]:
    from argus.api.chat.tool_results import tool_cards_from_metadata
    from argus.api.public_excerpts import _owned_run

    try:
        cards = tool_cards_from_metadata(message.metadata or {})
        bindings = [
            PublicExcerptToolSource(
                message_id=message.id,
                artifact_id=card.artifact_id,
                input_revision=card.input_revision,
            )
            for card in cards
        ]
    except ValueError:
        refuse("unsupported_turn")
    metadata = message.metadata or {}
    if "research" in metadata:
        project_research_turn(
            message=message,
            question=question,
            owner_note=owner_note,
            language=context.conversation.language,
            private_ids=private_ids,
        )
    run_ids = list(
        dict.fromkeys(
            [job["result_run_id"] for job in jobs if job.get("result_run_id")]
            + ([_run_id(message)] if _run_id(message) else [])
        )
    )
    artifacts = []
    for run_id in run_ids:
        run = _owned_run(user_id=context.user.id, run_id=run_id)
        artifact = next(
            (
                a
                for a in context.artifacts
                if a.source_run_id == run_id and a.artifact_type == "backtest"
            ),
            None,
        )
        if (
            run is None
            or run.conversation_id != context.conversation.id
            or artifact is None
        ):
            refuse("unsupported_backtest")
        # The existing result owner proves completeness; the declaration supplies
        # the actual shared presentation. No public facts are reconstructed here.
        project_backtest_turn(
            run=run,
            title=artifact.title,
            owner_note=owner_note,
            language=context.conversation.language,
            private_ids=(*private_ids, run_id),
        )
        artifacts.append(artifact)
    return (
        project_tool_turn(
            cards=cards,
            question=question,
            owner_note=owner_note,
            language=context.conversation.language,
            private_ids=private_ids,
        ),
        artifacts,
        run_ids,
        bindings,
    )


def receipt_candidates(*, user: User, conversation_id: str) -> PublicExcerptCandidates:
    context = _context(user, conversation_id)
    candidates = []
    for message in context.messages:
        if message.role != "assistant":
            continue
        values = dict(message_id=message.id, question=None)
        try:
            request = _question(context, message, _job(context, message))
            values["question"] = request.content if request else None
            leaf, _, _, _ = _project(context, message, None)
            candidates.append(
                PublicExcerptCandidate(**values, kind=leaf.kind, eligible=True)
            )
        except PublicExcerptSourceError as error:
            candidates.append(
                PublicExcerptCandidate(
                    **values, eligible=False, reason=error.reason, field=error.field
                )
            )
    return PublicExcerptCandidates(items=candidates)


def _selection(
    user: User, conversation_id: str, message_ids: list[str], owner_note: str | None
) -> tuple[
    SelectionContext,
    list[Message],
    list[Any],
    list[Any],
    list[str],
    list[PublicExcerptToolSource],
    str,
]:
    if not 1 <= len(message_ids) <= PUBLIC_EXCERPT_MAX_TURNS or len(
        set(message_ids)
    ) != len(message_ids):
        refuse("invalid_selection")
    context = _context(user, conversation_id)
    chosen = [m for m in context.messages if m.id in message_ids]
    if len(chosen) != len(message_ids):
        refuse("invalid_selection")
    leaves, artifacts, run_ids, bindings = [], [], [], []
    for message in chosen:
        leaf, selected_artifacts, selected_runs, selected_bindings = _project(
            context, message, owner_note
        )
        leaves.append(leaf)
        artifacts.extend(selected_artifacts)
        run_ids.extend(selected_runs)
        bindings.extend(selected_bindings)
    identity = sorted(message_ids)
    if bindings:
        identity = [identity, [binding.model_dump(mode="json") for binding in bindings]]
    key = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return context, chosen, leaves, artifacts, run_ids, bindings, key


def _existing(
    repository: Any,
    *,
    user: User,
    artifacts: list[Any],
    count: int,
    key: str,
    bindings: list[PublicExcerptToolSource],
) -> PublicExcerptSnapshot | None:
    if count == 1 and artifacts and not bindings:
        existing = repository.get_live_public_excerpt_for_artifact(
            owner_id=user.id, evidence_artifact_id=artifacts[0].id
        )
        if existing is not None:
            return existing
    return repository.get_live_public_excerpt_for_selection(
        owner_id=user.id, selection_key=key
    )


def preview_receipt_for_messages(
    *, user: User, conversation_id: str, message_ids: list[str], owner_note: str | None
) -> PublicExcerptPreview:
    from argus.api.public_excerpts import public_excerpt_repository

    _, _, leaves, artifacts, _, bindings, key = _selection(
        user, conversation_id, message_ids, owner_note
    )
    existing = _existing(
        public_excerpt_repository(),
        user=user,
        artifacts=artifacts,
        count=len(leaves),
        key=key,
        bindings=bindings,
    )
    payload = existing.payload if existing else PublicExcerptTurnsPayload(turns=leaves)
    return PublicExcerptPreview(
        payload=payload,
        payload_digest=payload_digest(payload),
        kind=document_kind(payload),
        existing_receipt=snapshot_list_item(existing) if existing else None,
    )


def create_receipt_for_messages(
    *,
    user: User,
    conversation_id: str,
    message_ids: list[str],
    owner_note: str | None,
    expected_digest: str,
    expected_tool_source: PublicExcerptToolSource | None = None,
) -> tuple[PublicExcerptSnapshot, bool]:
    from argus.api.public_excerpts import (
        EvidenceReceiptSourceChangedError,
        EvidenceReceiptSourceMissingError,
        _is_source_refusal,
        public_excerpt_repository,
    )

    _, chosen, leaves, artifacts, run_ids, bindings, key = _selection(
        user, conversation_id, message_ids, owner_note
    )
    if expected_tool_source is not None and expected_tool_source not in bindings:
        raise EvidenceReceiptSourceChangedError("That source changed.")
    repository = public_excerpt_repository()
    existing = _existing(
        repository,
        user=user,
        artifacts=artifacts,
        count=len(chosen),
        key=key,
        bindings=bindings,
    )
    payload = existing.payload if existing else PublicExcerptTurnsPayload(turns=leaves)
    if payload_digest(payload) != expected_digest:
        refuse("preview_changed")
    if existing is not None:
        return existing, False
    title = (
        leaves[0].question
        if leaves[0].kind in {"research_answer", "tool_result"}
        else leaves[0].idea_title
    )
    snapshot = PublicExcerptSnapshot(
        id=api_state.store.new_id(),
        public_id=new_public_excerpt_id(),
        owner_id=user.id,
        evidence_artifact_id=artifacts[0].id
        if len(chosen) == 1 and artifacts and not bindings
        else None,
        source_conversation_id=conversation_id,
        source_run_id=run_ids[0] if len(chosen) == 1 and run_ids else None,
        source_message_ids=[m.id for m in chosen],
        source_tool_bindings=bindings,
        source_run_ids=run_ids,
        source_artifact_ids=[a.id for a in artifacts],
        selection_key=key,
        kind=document_kind(payload),
        title=title,
        payload=payload,
        payload_digest=payload_digest(payload),
        created_at=datetime.now(timezone.utc),
    )
    try:
        result, created = repository.create_public_excerpt_snapshot(snapshot=snapshot)
        if result.payload_digest != expected_digest:
            refuse("preview_changed")
        return result, created
    except Exception as error:
        if isinstance(
            error, EvidenceReceiptSourceChangedError
        ) or "public_excerpt_source_changed" in str(error):
            refuse("preview_changed")
        if _is_source_refusal(error):
            raise EvidenceReceiptSourceMissingError(
                "That source is not available."
            ) from error
        raise


def create_receipt_for_artifact_adapter(
    *, user: User, artifact_id: str, owner_note: str | None
) -> tuple[PublicExcerptSnapshot, bool]:
    from argus.api.public_excerpts import _owned_artifact, public_excerpt_repository

    artifact, conversation = _owned_artifact(user_id=user.id, artifact_id=artifact_id)
    existing = public_excerpt_repository().get_live_public_excerpt_for_artifact(
        owner_id=user.id, evidence_artifact_id=artifact_id
    )
    if existing is not None:
        return existing, False
    if conversation is None:
        refuse("unsupported_backtest")
    context = _context(user, conversation.id)
    candidates = [
        m
        for m in context.messages
        if m.role == "assistant"
        and (
            _run_id(m) == artifact.source_run_id
            or (_job(context, m) or {}).get("result_run_id") == artifact.source_run_id
        )
    ]
    if not candidates:
        refuse("unsupported_backtest")
    # The first persisted result message is the card's canonical sharing lineage.
    message_ids = [candidates[0].id]
    preview = preview_receipt_for_messages(
        user=user,
        conversation_id=conversation.id,
        message_ids=message_ids,
        owner_note=owner_note,
    )
    return create_receipt_for_messages(
        user=user,
        conversation_id=conversation.id,
        message_ids=message_ids,
        owner_note=owner_note,
        expected_digest=preview.payload_digest,
    )
