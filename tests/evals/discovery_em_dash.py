"""Issue #644 discovery em-dash evidence and the free punctuation gate.

The two captured replies stay as raw evidence. This module detects U+2014
only. U+2013 en dash is outside the founder-locked copy rule
(`.agent/rules/coding-standards.md`, 2026-08-04). The check is
language-independent, so English and es-419 use the same helper.

Runtime owns the writer fix. `src/argus/domain/visible_reply.py` already
rewrites em dashes at the visibility boundary. This module does not
rewrite prose and does not add a second sanitizer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EM_DASH = "\u2014"
# U+2013 en dash is not this rule. Do not add it to the detector.
DEFAULT_FIXTURE_PATH = Path(__file__).with_name("discovery_em_dash_regression.json")
ISSUE_644_CASE_IDS = (
    "asset_discovery_trending_crypto_exact_issue_344",
    "asset_discovery_not_capability_question_issue_244",
)


@dataclass(frozen=True)
class DiscoveryEmDashEvidence:
    id: str
    sha256: str
    text: str

    def digest(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def prose_contains_em_dash(prose: str) -> bool:
    """Return True when user-facing prose contains U+2014.

    Hyphens and U+2013 en dashes do not count.
    """
    return EM_DASH in prose


def assert_no_em_dash(prose: str) -> None:
    """Fail when user-facing prose contains U+2014.

    Runtime satisfies this later by fixing generation, in English and
    es-419, through the existing `rewrite_visible_reply` owner. Do not
    rewrite preserved #644 evidence to make this pass.
    """
    if not prose_contains_em_dash(prose):
        return
    count = prose.count(EM_DASH)
    index = prose.index(EM_DASH)
    raise AssertionError(
        "user-facing prose contains U+2014 em dash "
        f"({count} occurrence(s); first at index {index})"
    )


def load_discovery_em_dash_evidence(
    path: Path | None = None,
) -> tuple[DiscoveryEmDashEvidence, ...]:
    payload = json.loads((path or DEFAULT_FIXTURE_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "discovery_em_dash_regression/v1":
        raise ValueError("unsupported discovery em-dash fixture schema")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("discovery em-dash fixture must list cases")
    return tuple(_parse_case(raw) for raw in raw_cases)


def _parse_case(raw: Any) -> DiscoveryEmDashEvidence:
    if not isinstance(raw, dict):
        raise ValueError("discovery em-dash case must be an object")
    case_id = raw.get("id")
    digest = raw.get("sha256")
    text = raw.get("text")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("discovery em-dash case is missing id")
    if not isinstance(digest, str) or not digest:
        raise ValueError(f"{case_id} is missing sha256")
    if not isinstance(text, str) or not text:
        raise ValueError(f"{case_id} is missing text")
    return DiscoveryEmDashEvidence(id=case_id, sha256=digest, text=text)
