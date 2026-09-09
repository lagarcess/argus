"""The shared applied-or-disclosed contract for edits to an artifact.

Adapters supply typed application facts. This module never interprets input,
knows an artifact's fields, or generates user-facing prose.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def complete_edit_disclosure(
    *,
    requested: Iterable[tuple[str, str]],
    materialized_targets: set[str],
    has_changes: bool,
    unapplied: Iterable[Mapping[str, str]] = (),
    note: str | None = None,
) -> dict[str, Any] | None:
    """Return a disclosure unless the requested edit is fully accounted for.

    A request can already match the artifact, or fail to produce any typed
    operation. Neither permits a silent card re-issue: the adapter must report
    whether anything changed. Unknown intent gets a generic typed receipt,
    never a guessed target. Specific refusals remain authoritative over notes.
    """
    entries = [dict(entry) for entry in unapplied]
    accounted_targets = materialized_targets | {entry["target"] for entry in entries}
    for op, target in requested:
        if target not in accounted_targets:
            entries.append({"op": op, "target": target, "reason": "not_materialized"})
            accounted_targets.add(target)
    if not has_changes and not entries:
        entries.append(
            {"op": "edit", "target": "requested_change", "reason": "no_change_applied"}
        )
    voice = str(note or "").strip()
    if not entries and not voice:
        return None
    disclosure: dict[str, Any] = {"unapplied": entries}
    if voice:
        disclosure["note"] = voice
    return disclosure
