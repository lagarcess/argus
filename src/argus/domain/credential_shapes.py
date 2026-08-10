"""Recognize credential-shaped text by its grammar rather than by its length.

A secret is identifiable from its own structure: an issuer prefix, a segment
count, a scheme keyword, a PEM banner, or userinfo in a URL. Length is a weak
proxy for the same question and fails in both directions, so it is not the test
here. ``AKIAIOSFODNN7EXAMPLE`` is twenty characters and a live AWS key id;
``consistency beat every clever entry rule`` is longer and is prose.

Used by two callers with different jobs. Committed eval prose is redacted, so
over-firing there costs a marker in an internal artifact. A public receipt is
frozen at creation and can never be edited, so the owner note is refused instead
and the owner fixes it while they still can. That is why the rules here key on
the value's own grammar and not on a nearby key name: `the secret: consistency`
names a credential and carries none.
"""

from __future__ import annotations

import os
import re

_MIN_ENVIRONMENT_SECRET_LENGTH = 12
_SECRET_ENVIRONMENT_NAME = re.compile(
    r"API_?KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|PRIVATE_KEY|SERVICE_ROLE"
)

# A JWS carries three segments and a JWE five, so consume every segment rather
# than a fixed three.
JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+){2,}")
BEARER_PATTERN = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{12,}")
# Issuer-prefixed keys: Stripe sk_/pk_/rk_, Slack xoxb-/xoxp-, GitHub ghp_/ghs_
# and the newer github_pat_.
PREFIXED_KEY_PATTERN = re.compile(
    r"\b(?:github_pat_[A-Za-z0-9_]{12,}"
    r"|(?:sk|pk|rk|ak|xoxb|xoxp|xoxa|xoxs|ghp|ghs|ghu|gho|glpat)"
    r"[-_][A-Za-z0-9._-]{12,})"
)
# AWS and Twilio style identifiers: an uppercase issuer prefix then base32-ish
# body, all caps, which is not a shape prose produces.
UPPERCASE_KEY_PATTERN = re.compile(
    r"\b(?:AKIA|ASIA|ABIA|ACCA|AIDA|PK|AK|CK|SK)[A-Z0-9]{16,}\b"
)
# A PEM banner names itself, so no entropy guess is needed.
PRIVATE_KEY_BANNER_PATTERN = re.compile(
    r"(?i)-{3,}\s*BEGIN[A-Z0-9 ]*PRIVATE KEY\s*-{3,}"
)
URL_USERINFO_PATTERN = re.compile(r"(?<=://)[^\s/:@]+:[^\s/@]+@")

# ── The credential key names, in one place ────────────────────────────────────────
#
# Both grammars below are generated from this list. They used to be two hand-written
# alternations that had to agree and did not: `csrf_token`, `xsrf_token` and
# `session_id` were classified as credential keys by one and ignored by the other, so
# `csrf_token=x` reached a public page while `password=x` did not. A list plus a
# generator makes that disagreement unrepresentable rather than merely fixed.
#
# Spaces stand for an optional separator, so "session id" covers session_id,
# session-id, sessionid and "session id" written out. Every name also matches its
# plural. The separator includes a literal space because people write notes, not
# config: "api key = hunter2" is the same disclosure as "api_key=hunter2", and the
# value is short enough that no shape rule would catch it.
CREDENTIAL_KEY_NAMES: tuple[str, ...] = (
    "api key",
    "access key",
    "access token",
    "auth",
    "auth token",
    "authorization",
    "bearer token",
    "client secret",
    "credential",
    "csrf token",
    "id token",
    "password",
    "passwd",
    "private key",
    "pwd",
    "refresh token",
    "secret",
    "session id",
    "session token",
    "signature",
    "token",
    "xsrf token",
)


def _key_alternation(names: tuple[str, ...]) -> str:
    """A regex alternation over the names, longest first.

    Longest first matters: with `token` ahead of `access token`, the shorter branch
    wins and the captured key is only the tail of the real one.
    """
    parts = [
        r"[_\- ]?".join(re.escape(word) for word in name.split()) + "s?"
        for name in names
    ]
    return "(?:" + "|".join(sorted(parts, key=len, reverse=True)) + ")"


_CREDENTIAL_KEY = _key_alternation(CREDENTIAL_KEY_NAMES)
CREDENTIAL_KEY_PATTERN = _CREDENTIAL_KEY

# The key is the signal, so the value is not inspected at all. Anything after the
# separator is the secret, whatever its length or characters: a one character
# password is still a password, and `P@ssw0rd` is not less of one for containing
# punctuation. Guarding on the value's size or its character class is what let
# `password=hunter2` and `password=P@ssw0rd` through.
_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    rf"(?i)(?P<lead>\b\w+[ \t]+)?"
    rf"[\"']?\b(?P<key>{_CREDENTIAL_KEY})\b[\"']?[ \t]*"
    r"(?P<separator>[:=])[ \t]*(?P<value>\S)"
)

# `secret: consistency` is a sentence and `api_key: abc` is an assignment, and the
# difference is the article in front. Only the colon form needs this: prose does not
# write `secret = something`, so `=` is taken at face value.
_PROSE_DETERMINERS = frozenset(
    {
        "the", "a", "an", "my", "our", "your", "his", "her", "their", "its",
        "this", "that", "these", "those", "no", "any", "some", "every", "each",
        "one", "another", "whose",
    }
)

# Ordered narrowest first so the reported kind names the most specific match.
CREDENTIAL_SHAPE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", PRIVATE_KEY_BANNER_PATTERN),
    ("jwt", JWT_PATTERN),
    ("bearer_token", BEARER_PATTERN),
    ("api_key", PREFIXED_KEY_PATTERN),
    ("api_key", UPPERCASE_KEY_PATTERN),
    ("url_userinfo", URL_USERINFO_PATTERN),
)


def keyed_credential_in(text: str) -> bool:
    """True when the text assigns a value to something that names a credential.

    Additive to the shape rules above, which cover an unkeyed secret like a bare AWS
    key id. This covers the other direction: a value that looks like nothing on its
    own, announced by its key.
    """
    for match in _CREDENTIAL_ASSIGNMENT_RE.finditer(text):
        if match.group("separator") == "=":
            return True
        lead = (match.group("lead") or "").strip().lower()
        if lead in _PROSE_DETERMINERS:
            continue
        return True
    return False


def credential_shape_in(text: object) -> str | None:
    """Return the kind of the first credential shape found, or None."""
    if not isinstance(text, str) or not text:
        return None
    for kind, pattern in CREDENTIAL_SHAPE_RULES:
        if pattern.search(text):
            return kind
    if keyed_credential_in(text):
        return "keyed_secret"
    for secret in environment_secret_values():
        if secret in text:
            return "environment_secret"
    return None


def environment_secret_values() -> list[str]:
    """Actual secret values from this process's environment, longest first."""
    values = {
        value.strip()
        for name, value in os.environ.items()
        if _SECRET_ENVIRONMENT_NAME.search(name.upper())
        and len(value.strip()) >= _MIN_ENVIRONMENT_SECRET_LENGTH
    }
    # Longest first, so a secret that contains a shorter one is matched whole.
    return sorted(values, key=len, reverse=True)
