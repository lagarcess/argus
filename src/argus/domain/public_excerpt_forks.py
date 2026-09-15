"""Bounded receiver-owned copies of frozen public turns, with no execution state."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from argus.api.public_excerpt_schemas import (
    PublicExcerptDocument,
    PublicExcerptTurnsPayload,
)

FORK_TEXT_BYTES = 64 * 1024
FORK_PAYLOAD_BYTES = 512 * 1024


class ForkError(ValueError):
    def __init__(self, code: str, status: int = 409):
        self.code = code
        self.status = status
        super().__init__(code)


def fork_marker(user_id: str, request_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"argus:shared-fork:{user_id}:{request_id}"))


def _without_notes(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_notes(v) for k, v in value.items() if k != "owner_note"}
    if isinstance(value, list):
        return [_without_notes(v) for v in value]
    return value


def _clip(value: str, budget: int) -> str:
    raw = value.encode("utf-8")
    if len(raw) <= budget:
        return value
    return raw[: max(0, budget - 3)].decode("utf-8", errors="ignore") + "..."


def carried_messages(
    payload: PublicExcerptDocument,
    *,
    snapshot_at: datetime,
    public_id: str,
    request_id: str,
) -> list[dict[str, Any]]:
    turns = payload.turns if isinstance(payload, PublicExcerptTurnsPayload) else [payload]
    budget = FORK_TEXT_BYTES // (2 * len(turns))
    messages = []
    for index, turn in enumerate(turns):
        card = _without_notes(turn.model_dump(mode="json"))
        question = _clip(
            str(card.get("question") or card.get("idea_title") or ""), budget
        )
        answer = card.get("answer_text") or card.get("answer") or ""
        # Legacy calculation documents encode answer as a fact object.
        answer = answer if isinstance(answer, str) else ""
        facts = {
            k: v
            for k, v in card.items()
            if k not in {"question", "answer_text", "visual"}
            and not (k == "answer" and isinstance(v, str))
        }
        facts["snapshot_at"] = snapshot_at.isoformat()
        fact_text = (
            json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
            if card.get("kind") != "answer"
            else ""
        )
        fact_bytes = len(fact_text.encode("utf-8")) + (1 if fact_text else 0)
        if fact_bytes > budget - 3:
            raise ForkError("receipt_context_too_large", 413)
        answer_budget = budget - fact_bytes
        content = _clip(answer, answer_budget) + ("\n" + fact_text if fact_text else "")
        for key in ("question", "answer_text", "answer"):
            if isinstance(card.get(key), str):
                card[key] = _clip(
                    card[key], budget if key == "question" else answer_budget
                )
        provenance = {
            "snapshot_at": snapshot_at.isoformat(),
            "public_id": public_id,
            "request_id": request_id,
            "turn_index": index,
        }
        messages.append(
            {
                "role": "user",
                "content": question,
                "metadata": {"shared_conversation": provenance},
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": content,
                "metadata": {"shared_conversation": {**provenance, "card": card}},
            }
        )
    if (
        len(json.dumps(messages, ensure_ascii=False, separators=(",", ":")).encode())
        > FORK_PAYLOAD_BYTES
    ):
        raise ForkError("receipt_context_too_large", 413)
    return messages
