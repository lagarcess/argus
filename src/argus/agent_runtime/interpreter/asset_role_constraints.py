"""Typed asset-role constraints for artifact edit materialization.

The single-choice ``asset_universe_operation`` label cannot say whether
"replace" meant "this is the whole new set" or "swap these members"; the
typed inclusion/exclusion roles can. These helpers let roles outrank carried
or context-injected ``asset_universe`` copies and prove a materialization
satisfies the roles, with a receipt whenever they override or refuse
(AGENTS.md: redundancy over a model read must be observable).
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

    When exclusions name current card members, the user said what leaves and
    everything un-named stays, whatever the operation label says ("remove
    AAPL and replace with TSLA and GOOGL" keeps MSFT). The label breaks ties
    only where the roles are silent: a replace with pure keep-out exclusions
    states the whole new set, and anything else licenses no drop at all.
    """

    grounded_primary_requested = {
        symbol
        for symbol in primary_requested
        if symbol in current or symbol in grounded or symbol in primary_inclusions
    }
    removed = current - materialized
    unexplained = materialized - (
        current | primary_inclusions | grounded_primary_requested | grounded
    )
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
        and not (primary_exclusions & materialized)
        and not unexplained
        and role_ok
    )
    if not matches:
        logger.info(
            "Artifact edit role constraints refused a materialization "
            "inclusions_landed={} exclusions_left={} removals_licensed={} "
            "unexplained={}",
            primary_inclusions <= materialized,
            not (primary_exclusions & materialized),
            role_ok,
            sorted(unexplained),
            inclusions_landed=primary_inclusions <= materialized,
            exclusions_left=not (primary_exclusions & materialized),
            removals_licensed=role_ok,
            unexplained=sorted(unexplained),
        )
    return matches
