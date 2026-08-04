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
    "clear. Set needs_current_facts=true only when a correct answer "
    "requires facts newer than your knowledge (recent IPOs, this week's "
    "movers, current rankings), the user asks for current or up-to-date "
    "candidates, or explicitly asks to search current sources, in any "
    "language; stable category/peer questions are false. Leave "
    "candidate_strategy_draft empty on asset_discovery "
    "turns; the user is asking who exists, not yet configuring a test. "
    "Ordinary 'what should I try next?' follow-ups stay result_followup "
    "with next_experiment; questions about what Argus supports stay "
    "educational_question; a direct request to test a named asset is "
    "never asset_discovery. A pending confirmation or draft does not "
    "change this classification: 'what companies similar to X could I "
    "try?' is asset_discovery even while a run is waiting for approval — "
    "never answer it as an edit to the pending run, and never claim "
    "Argus cannot find similar assets. "
)
