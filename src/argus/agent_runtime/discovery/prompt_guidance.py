from __future__ import annotations

# Tail of the interpreter's semantic_turn_act enumeration (retry_failed_action,
# unsupported_request, asset_discovery). Kept beside the discovery composer so
# the classification boundary and the route that consumes it evolve together.
DISCOVERY_ACT_GUIDANCE = (
    "retry_failed_action when the user asks to try again, retry, rerun the same "
    "one, or otherwise repeat the latest failed run without changing the idea, "
    "unsupported_request when the user asks for unsupported capabilities, "
    "and asset_discovery when the user explicitly asks Argus to find, "
    "discover, list, or suggest which assets exist to test (set intent "
    "to conversation_followup for these turns) — by category "
    "('what cybersecurity stocks could I test?'), by peer similarity "
    "('find companies similar to Nvidia'), or for comparison candidates "
    "('what else in Costco's category could I compare?'), in any language. "
    "For asset_discovery turns, always fill the asset_discovery payload: "
    "relationship (category, peer, or comparison), category_description "
    "with the plain category phrase when one exists, anchor_symbols with "
    "known tickers the user is anchoring on, and asset_class_hint when "
    "clear. Leave candidate_strategy_draft empty on asset_discovery "
    "turns; the user is asking who exists, not yet configuring a test. "
    "Ordinary 'what should I try next?' follow-ups stay result_followup "
    "with next_experiment; questions about what Argus supports stay "
    "educational_question; a direct request to test a named asset is "
    "never asset_discovery. "
)
