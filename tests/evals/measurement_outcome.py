"""What actually reached the user, and whether it was enough.

Routing assertions can all pass while the reply is a dead end. This
module owns the one question that catches that: did the turn end
somewhere the user can act on, or name what it could not do. Kept apart
from the harness so the projection and its comparison stay one idea.
"""

from __future__ import annotations

from typing import Any


def offered_to_user(
    *,
    final_patch: dict[str, Any],
    interpret_patch: dict[str, Any],
    launch_payload: dict[str, Any],
    assistant_text: str = "",
) -> dict[str, Any]:
    """Project the turn's user-actionable surface out of the stage patch.

    A discovery row, a next-experiment row, a recovery option, or a launch
    payload are the things a user can actually press. Everything else in the
    patch is prose or provenance.
    """

    def _patch_value(key: str) -> Any:
        value = final_patch.get(key)
        return interpret_patch.get(key) if value is None else value

    discovery = _patch_value("discovery")
    discovery = discovery if isinstance(discovery, dict) else {}
    rows = [row for row in (discovery.get("candidates") or []) if isinstance(row, dict)]
    discovery_symbols = [
        str(row.get("symbol") or "").upper() for row in rows if row.get("symbol")
    ]

    experiments = _patch_value("next_experiments")
    experiments = experiments if isinstance(experiments, dict) else {}
    experiment_kinds = [
        str(row.get("kind") or "")
        for row in (experiments.get("rows") or [])
        if isinstance(row, dict) and row.get("kind")
    ]

    clarification = _patch_value("clarification")
    clarification = clarification if isinstance(clarification, dict) else {}
    # typed_clarification_contract writes options as a sibling of payload;
    # payload carries strategy, coverage and raw_value only.
    option_ids = [
        str(option.get("id") or "")
        for option in (clarification.get("options") or [])
        if isinstance(option, dict) and option.get("id")
    ]

    recovery = _patch_value("recovery")
    recovery = recovery if isinstance(recovery, dict) else {}

    # The sidecar's list is what the turn dropped; the assertion is about
    # what the user was told. Reading the sidecar let a reply that named
    # nothing pass a check written to require naming, so only drops that
    # actually survive into the prose count here.
    dropped = [str(name) for name in (discovery.get("unverified_names") or []) if str(name)]
    haystack = _alnum(assistant_text)
    named_unavailable = [name for name in dropped if _name_appears(name, haystack)]

    return {
        "discovery_symbols": discovery_symbols,
        "next_experiment_kinds": experiment_kinds,
        "recovery_option_ids": option_ids,
        "recovery_code": recovery.get("code"),
        "named_unavailable": named_unavailable,
        "dropped_not_named": [name for name in dropped if name not in named_unavailable],
        "actionable": bool(
            discovery_symbols or experiment_kinds or option_ids or launch_payload
        ),
    }


def _alnum(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def _name_appears(name: str, haystack: str) -> bool:
    """Did the reply actually say this name, in any spelling the reader sees."""
    whole = _alnum(name)
    if whole and whole in haystack:
        return True
    first = name.split()[0] if name.split() else ""
    compact = _alnum(first)
    return len(compact) >= 4 and compact in haystack


def compare_offered(
    expected: dict[str, Any],
    actual: Any,
    failures: list[str],
) -> None:
    """Assert the turn ended somewhere the user can act on.

    Routing assertions can all pass while the reply is a dead end. This is
    the check that a case cannot be green unless something usable, or a
    named limitation with a runnable alternative, actually reached the user.
    """
    if not isinstance(actual, dict):
        failures.append(f"offered: expected payload {expected!r}, got {actual!r}")
        return
    if expected.get("actionable") is True and not actual.get("actionable"):
        failures.append(
            "offered.actionable: nothing the user can act on reached the turn "
            f"(offered={actual!r})"
        )
    minimum_rows = expected.get("min_discovery_rows")
    if isinstance(minimum_rows, int):
        rows = actual.get("discovery_symbols") or []
        if len(rows) < minimum_rows:
            failures.append(
                f"offered.min_discovery_rows: expected at least {minimum_rows}, "
                f"got {len(rows)} ({rows!r})"
            )
    # A turn that hands the user nothing owes an account of what it found and
    # could not use; that empty turn is the dead end this guards. A turn that
    # hands over something runnable owes no such account, because listing
    # discards beside usable rows is noise to the reader. Founder-locked
    # 2026-08-19, and it is why the pipeline's silent-filtering contract in
    # `TestDropDisclosures` survives unchanged.
    if (
        expected.get("names_unavailable") is True
        and not actual.get("actionable")
        and not (actual.get("named_unavailable") or [])
    ):
        failures.append(
            "offered.names_unavailable: the turn offered nothing the user can "
            "act on and did not name what it found and could not use"
        )
    expected_options = expected.get("recovery_option_ids_include_any")
    if expected_options:
        option_ids = {str(item) for item in (actual.get("recovery_option_ids") or [])}
        if not option_ids.intersection({str(item) for item in expected_options}):
            failures.append(
                f"offered.recovery_option_ids_include_any: expected any of "
                f"{list(expected_options)!r}, got {sorted(option_ids)!r}"
            )
