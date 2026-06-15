from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

MAX_FEEDBACK_MESSAGE_LENGTH = 5000
MAX_FEEDBACK_CONTEXT_TEXT_LENGTH = 256
MAX_FEEDBACK_TAGS = 12
MAX_FEEDBACK_TAG_LENGTH = 40

_SCALAR_CONTEXT_KEYS = (
    "source",
    "surface",
    "message_id",
    "conversation_id",
    "message_kind",
    "artifact_id",
    "artifact_type",
    "artifact_status",
    "result_run_id",
    "strategy_id",
    "saved_strategy_id",
    "confirmation_id",
    "confirmation_state",
    "confirmation_status",
    "backtest_job_id",
    "backtest_job_status",
    "failure_code",
    "rating",
    "timestamp",
    "retryable",
)

_RENAMED_CONTEXT_KEYS = {
    "hasAttachments": "has_attachments",
    "attachmentCount": "attachment_count",
}


def sanitize_feedback_context(context: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}

    for key in _SCALAR_CONTEXT_KEYS:
        value = _sanitize_scalar(context.get(key))
        if value is not None:
            sanitized[key] = value

    for source_key, target_key in _RENAMED_CONTEXT_KEYS.items():
        value = _sanitize_scalar(context.get(source_key))
        if value is not None:
            sanitized[target_key] = value

    tags = _sanitize_tags(context.get("tags"))
    if tags:
        sanitized["tags"] = tags

    page_path = _safe_page_path(context.get("url"))
    if page_path is None:
        metadata = context.get("metadata")
        if isinstance(metadata, Mapping):
            page_path = _safe_page_path(metadata.get("path"))
    if page_path is not None:
        sanitized["page_path"] = page_path

    return sanitized


def _sanitize_scalar(value: Any) -> str | int | float | bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return text[:MAX_FEEDBACK_CONTEXT_TEXT_LENGTH]
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return None


def _sanitize_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        tag = item.strip()
        if not tag:
            continue
        tags.append(tag[:MAX_FEEDBACK_TAG_LENGTH])
        if len(tags) >= MAX_FEEDBACK_TAGS:
            break
    return tags


def _safe_page_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None

    parsed = urlsplit(raw)
    if parsed.scheme or parsed.netloc:
        path = parsed.path
    else:
        path = raw.split("?", 1)[0].split("#", 1)[0]

    if not path.startswith("/"):
        return None

    parts = [":id" if _is_uuid_like(part) else part for part in path.split("/")]
    safe_path = "/".join(parts) or "/"
    return safe_path[:MAX_FEEDBACK_CONTEXT_TEXT_LENGTH]


def _is_uuid_like(value: str) -> bool:
    if not value:
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True
