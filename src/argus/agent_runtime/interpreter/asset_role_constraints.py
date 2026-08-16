"""Typed asset-role constraints for artifact edit materialization.

The single-choice ``asset_universe_operation`` label cannot distinguish "this
is the whole new set" from "swap these members"; the typed inclusion/exclusion
roles can, so roles outrank carried or context-injected ``asset_universe``
copies. Every symbol in an accepted materialization must trace to typed
evidence: the current card, a typed inclusion, or a grounded member of the
flat request — a mere message mention never adds an asset. Overrides log here
and stamp ``asset_exclusions_outranked_universe_copy`` on the accepted plan's
response; a refusal's turn-correlated receipt is the fallback clarification's
``asset_universe_operation_needs_clarification`` code.
"""

from __future__ import annotations

from loguru import logger


def primary_assets_with_exclusions_removed(
    primary_assets: set[str],
    primary_asset_exclusions: set[str],
) -> set[str]:
    """A typed exclusion outranks a carried or context-injected copy of the
    same symbol in ``asset_universe``; only an inclusion-vs-exclusion overlap
    is a real contradiction."""

    overlap = primary_assets & primary_asset_exclusions
    if not overlap:
        return primary_assets
    logger.info(
        "Artifact edit coherence: typed exclusions outrank asset_universe "
        "copies overlap={}",
        sorted(overlap),
        overlap=sorted(overlap),
    )
    return primary_assets - primary_asset_exclusions


def asset_role_constraints_satisfied(
    *,
    materialized: set[str],
    current: set[str],
    primary_requested: set[str],
    primary_inclusions: set[str],
    primary_exclusions: set[str],
    grounded: set[str],
    operation: str | None,
    planned_asset_replacement: bool,
) -> bool:
    """Prove a materialization satisfies the typed asset roles.

    Exclusions naming current card members license exactly those removals and
    everything un-named stays, whatever the operation label says; this swap
    reading deliberately outranks the whole-set reading of "replace" (the two
    are indistinguishable at the typed level, the locked eval fixture
    `action_chip_change_asset_compound_replace_issue_188` encodes the swap,
    and a re-ask on a whole-set turn beats a silent wipe of un-named
    members). The label breaks ties only where the roles are silent: a
    replace with pure keep-out exclusions states the whole new set, and
    anything else licenses no drop at all.
    """

    grounded_primary_requested = {
        symbol
        for symbol in primary_requested
        if symbol in current or symbol in grounded or symbol in primary_inclusions
    }
    removed = current - materialized
    # A materialized symbol needs a typed role or a grounded flat request;
    # a bare message mention ("worse than NVDA lately") never adds an asset.
    unexplained = materialized - (
        current | primary_inclusions | grounded_primary_requested
    )
    # Every requested addition that survives the exclusions must land;
    # otherwise half of a compound add vanishes with no disclosure.
    dropped_requested = (grounded_primary_requested - primary_exclusions) - materialized
    card_exclusions = primary_exclusions & current
    if card_exclusions:
        role_ok = removed <= primary_exclusions
    elif (
        operation == "replace" or (operation is None and planned_asset_replacement)
    ) and (grounded_primary_requested | primary_inclusions):
        role_ok = materialized == (grounded_primary_requested | primary_inclusions)
    else:
        role_ok = not removed
    matches = (
        bool(materialized)
        and materialized != current
        and primary_inclusions <= materialized
        and not dropped_requested
        and not (primary_exclusions & materialized)
        and not unexplained
        and role_ok
    )
    if not matches:
        logger.info(
            "Artifact edit role constraints refused a materialization "
            "inclusions_landed={} requested_landed={} exclusions_left={} "
            "removals_licensed={} unexplained={}",
            primary_inclusions <= materialized,
            not dropped_requested,
            not (primary_exclusions & materialized),
            role_ok,
            sorted(unexplained),
            inclusions_landed=primary_inclusions <= materialized,
            requested_landed=not dropped_requested,
            exclusions_left=not (primary_exclusions & materialized),
            removals_licensed=role_ok,
            unexplained=sorted(unexplained),
        )
    return matches
