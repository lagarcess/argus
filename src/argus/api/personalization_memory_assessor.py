"""Backend-owned sensitivity assessment for memory candidate content.

The API layer is the only assessment authority: clients cannot claim a status,
and every candidate enters storage only through this module. Any classifier
failure yields UNASSESSED, which policy suppresses, so nothing unclassified is
ever stored.
"""

from __future__ import annotations

from collections.abc import Callable

from argus.llm.memory_sensitivity import (
    MemorySensitivityVerdict,
    classify_memory_sensitivity,
)
from argus.memory.contracts import (
    MemorySensitivityFlag,
    SensitivityAssessment,
    SensitivityStatus,
)

# Never storable regardless of user confirmation or any claimed status.
NEVER_STORABLE_FLAGS = frozenset(
    {
        MemorySensitivityFlag.BROKER_CREDENTIAL,
        MemorySensitivityFlag.RAW_CONVERSATION,
    }
)

SensitivityClassifier = Callable[[str], MemorySensitivityVerdict | None]

_classifier: SensitivityClassifier = classify_memory_sensitivity


def configure_sensitivity_classifier(
    classifier: SensitivityClassifier | None,
) -> None:
    """Inject a classifier; None restores the OpenRouter-backed default."""

    global _classifier
    _classifier = classifier if classifier is not None else classify_memory_sensitivity


def candidate_content_for_assessment(
    *,
    label: str,
    value: str,
    future_benefit: str,
) -> str:
    return f"label: {label}\nvalue: {value}\nfuture benefit: {future_benefit}"


def assess_memory_content(content: str) -> SensitivityAssessment:
    """Classify content; the result is the only assessment storage may see.

    Fail-closed ladder: classifier failure or an unrecognized flag yields
    UNASSESSED; any flag, including a never-storable one claimed alongside a
    "clear" status, forces RESTRICTED. Policy suppresses both.
    """

    try:
        verdict = _classifier(content)
    except Exception:
        verdict = None
    if verdict is None:
        return SensitivityAssessment()
    try:
        flags = frozenset(MemorySensitivityFlag(flag) for flag in verdict.flags)
    except ValueError:
        return SensitivityAssessment()
    if flags or verdict.status != "clear":
        return SensitivityAssessment(
            status=SensitivityStatus.RESTRICTED,
            flags=flags,
        )
    return SensitivityAssessment(status=SensitivityStatus.CLEAR)
