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
_CREDENTIAL_ASSIGNMENT = rf"[\"']?{_CREDENTIAL_KEY}[\"']?\s*[:=]\s*"
# An auth value is a scheme followed by its credentials, so the space after the
# scheme name does not end the value.
_AUTH_SCHEME = r"(?:bearer|basic|digest|negotiate|token|apikey)"
_MARKER_PREFIX = "[redacted:"

# Every rule must consume a secret to its real end. A value's end comes from
# whatever opened it, never from the first plausible-looking delimiter: cutting
# early publishes the tail, and the shortened head can also fall under a length
# guard so the rule stops firing and publishes the whole value.
#
# Ordered: narrower structural rules run before the generic address rule, and
# quoted assignments run before unquoted ones.
_REDACTION_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        # A JWS carries three segments and a JWE five, so consume every segment
        # rather than a fixed three.
        "jwt",
        re.compile(r"eyJ[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+){2,}"),
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
        # A quoted value runs to its closing quote, whatever it contains.
        "credential_assignment",
        re.compile(rf'(?i)({_CREDENTIAL_ASSIGNMENT})"[^"\n]{{4,}}"'),
        r'\1"[redacted:credential_assignment]"',
    ),
    (
        "credential_assignment",
        re.compile(rf"(?i)({_CREDENTIAL_ASSIGNMENT})'[^'\n]{{4,}}'"),
        r"\1'[redacted:credential_assignment]'",
    ),
    (
        # An unterminated quote, as in a clipped log line, has no closing
        # delimiter to trust, so the line end is the only safe boundary.
        "credential_assignment",
        re.compile(rf"(?im)({_CREDENTIAL_ASSIGNMENT})[\"'][^\"'\n]{{4,}}$"),
        r"\1[redacted:credential_assignment]",
    ),
    (
        "credential_assignment",
        re.compile(
            rf"(?i)({_CREDENTIAL_ASSIGNMENT})((?:{_AUTH_SCHEME}\s+)?)"
            rf"[^\s,;&)}}\]\"']{{6,}}"
        ),
        r"\1\2[redacted:credential_assignment]",
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
        redacted, applied = _apply_rule(redacted, pattern, replacement)
        if applied:
            counts[kind] = counts.get(kind, 0) + applied
    return redacted, [{"kind": kind, "count": counts[kind]} for kind in sorted(counts)]


def _apply_rule(
    text: str,
    pattern: re.Pattern[str],
    replacement: str,
) -> tuple[str, int]:
    applied = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal applied
        # An earlier rule already removed this span; redacting it again would
        # report one secret as two.
        if _MARKER_PREFIX in match.group(0):
            return match.group(0)
        applied += 1
        return match.expand(replacement)

    return pattern.sub(replace, text), applied


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
