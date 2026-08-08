"""Serialize the exact assistant prose a judge scored, for failure attribution.

Retention is additive: nothing here may reach a verdict, a failed check, or a
status. Redaction and truncation shape the serialized copy only, never the
string handed to the judge.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

# The response-style contract asks for one or two short paragraphs, so this
# budget keeps conforming prose whole and clips only degenerate output.
PROSE_TEXT_RETENTION_LIMIT = 4000
# Judges react to closing capability claims as often as to opening tone, so the
# tail survives truncation instead of only the first N characters.
PROSE_TEXT_RETENTION_TAIL = 1500
PROSE_TEXT_ELISION_TEMPLATE = "\n[... {count} characters elided ...]\n"

_MIN_ENVIRONMENT_SECRET_LENGTH = 12
_SECRET_ENVIRONMENT_NAME = re.compile(
    r"API_?KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|PRIVATE_KEY|SERVICE_ROLE"
)
_CREDENTIAL_KEY = (
    r"(?:api[_-]?key|access[_-]?key|access[_-]?token|client[_-]?secret|secret"
    r"|token|password|passwd|authorization|signature)"
)

# Ordered: the narrower structural rules run before the generic address rule so
# a credential inside a URL is not relabelled as an email address.
_REDACTION_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "jwt",
        re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+"),
        "[redacted:jwt]",
    ),
    (
        "bearer_token",
        re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{12,}"),
        r"\1 [redacted:bearer_token]",
    ),
    (
        "api_key",
        re.compile(r"\b(?:sk|pk|rk|ak|xoxb|xoxp|ghp|ghs)[-_][A-Za-z0-9._-]{12,}"),
        "[redacted:api_key]",
    ),
    (
        "api_key",
        re.compile(r"\b(?:PK|AK|CK)[A-Z0-9]{16,}\b"),
        "[redacted:api_key]",
    ),
    (
        "url_userinfo",
        re.compile(r"(?<=://)[^\s/:@]+:[^\s/@]+@"),
        "[redacted:url_userinfo]@",
    ),
    (
        "credential_assignment",
        re.compile(
            # Brackets are excluded so an earlier rule's marker is not redacted
            # a second time and counted as a second secret.
            rf"(?i)([\"']?{_CREDENTIAL_KEY}[\"']?\s*[:=]\s*)[\"']?[^\s,;&)}}\[\]\"']{{6,}}"
        ),
        r"\1[redacted:credential_assignment]",
    ),
    (
        "email",
        re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]*\w"),
        "[redacted:email]",
    ),
)


def judged_prose_evidence(assistant_text: str) -> dict[str, Any]:
    """Return the retention record for the exact text supplied to the judge.

    ``text`` equals the judged string verbatim whenever ``truncated`` is false
    and ``redactions`` is empty; ``sha256`` and ``character_count`` always
    describe the judged string itself so two runs stay comparable.
    """
    redacted, redactions = redact_sensitive_text(assistant_text)
    retained, omitted = truncate_retained_text(redacted)
    return {
        "text": retained,
        "sha256": hashlib.sha256(assistant_text.encode("utf-8")).hexdigest(),
        "character_count": len(assistant_text),
        "truncated": omitted > 0,
        "omitted_character_count": omitted,
        "redactions": redactions,
    }


def redact_sensitive_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Strip credential-shaped and user-identifying spans from committed text."""
    counts: dict[str, int] = {}
    redacted = text
    for secret in _environment_secret_values():
        occurrences = redacted.count(secret)
        if occurrences:
            redacted = redacted.replace(secret, "[redacted:environment_secret]")
            counts["environment_secret"] = (
                counts.get("environment_secret", 0) + occurrences
            )
    for kind, pattern, replacement in _REDACTION_RULES:
        redacted, replaced = pattern.subn(replacement, redacted)
        if replaced:
            counts[kind] = counts.get(kind, 0) + replaced
    return redacted, [{"kind": kind, "count": counts[kind]} for kind in sorted(counts)]


def truncate_retained_text(text: str) -> tuple[str, int]:
    """Clip to the retention budget, keeping the head and the tail."""
    if len(text) <= PROSE_TEXT_RETENTION_LIMIT:
        return text, 0
    head_length = PROSE_TEXT_RETENTION_LIMIT - PROSE_TEXT_RETENTION_TAIL
    omitted = len(text) - PROSE_TEXT_RETENTION_LIMIT
    return (
        text[:head_length]
        + PROSE_TEXT_ELISION_TEMPLATE.format(count=omitted)
        + text[-PROSE_TEXT_RETENTION_TAIL:],
        omitted,
    )


def _environment_secret_values() -> list[str]:
    values = {
        value.strip()
        for name, value in os.environ.items()
        if _SECRET_ENVIRONMENT_NAME.search(name.upper())
        and len(value.strip()) >= _MIN_ENVIRONMENT_SECRET_LENGTH
    }
    # Longest first, so a secret that contains a shorter one is replaced whole.
    return sorted(values, key=len, reverse=True)
