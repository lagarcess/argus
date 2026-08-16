from __future__ import annotations

# Tail of the interpreter's semantic_turn_act enumeration (retry_failed_action,
# unsupported_request, asset_discovery) plus the act-independent
# asset_discovery payload read. Kept beside the discovery composer so the
# classification boundary and the route that consumes it evolve together.
DISCOVERY_ACT_GUIDANCE = (
    "retry_failed_action when the user asks to try again, retry, rerun the same "
    "one, or otherwise repeat the latest failed run without changing the idea, "
    "unsupported_request when the user asks for unsupported capabilities, "
    "and asset_discovery when finding assets is the turn's action. "
    "The asset_discovery payload is a separate read that does not depend on "
    "the act you chose: fill it whenever the user asks Argus to find, "
    "discover, list, suggest, or search for which assets exist — by "
    "category, by peer similarity, or for comparison candidates, in any "
    "language — even when the turn also reads as a question and you "
    "classified the act as educational_question or another value. The "
    "payload, not the act label, routes discovery. This includes messages "
    "that are follow-up actions Argus itself offered after a "
    "general-knowledge candidate list, such as 'Search current sources "
    "for: <category>'. On payload turns set intent to "
    "conversation_followup, and fill relationship (category, peer, or "
    "comparison), category_description with the plain category phrase "
    "when one exists, anchor_symbols with known tickers the user is "
    "anchoring on, and asset_class_hint when clear. Set "
    "needs_current_facts=true only when a correct answer requires facts "
    "newer than your knowledge (recent IPOs, this week's movers, current "
    "rankings), the user asks for current or up-to-date candidates, or "
    "explicitly asks to search current sources, in any language; stable "
    "category/peer questions are false. Leave candidate_strategy_draft "
    "empty on payload turns; the user is asking who exists, not yet "
    "configuring a test. Never fill the payload for ordinary 'what should "
    "I try next?' follow-ups (those stay result_followup with "
    "next_experiment), for questions about whether Argus supports finding "
    "assets (educational_question, no payload), or for a direct request "
    "to test a named asset. A pending confirmation or draft does not "
    "change this read: 'what companies similar to X could I try?' still "
    "fills the payload even while a run is waiting for approval — never "
    "answer it as an edit to the pending run, and never claim Argus "
    "cannot find similar assets. "
)
