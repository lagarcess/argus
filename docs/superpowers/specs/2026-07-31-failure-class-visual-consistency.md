# Failure-class visual consistency — scope note

Anchored by [PR #311, comment 5141228550](https://github.com/lagarcess/argus/pull/311#issuecomment-5141228550)
— founder's own diagnosis, already root-caused, treated below as the
proven first item, not the whole scope. Founder direction: this lane is
about consistency across every place Argus shows failure in the UI, not
just this one pair — the root cause (no shared source of truth for how
failure gets visually signaled) is structural, so one patched pair doesn't
stop the next one from happening.

"Everywhere we show failure" needs a boundary or it never ends. This lane
runs in two phases so it stays broad in coverage but has an actual
stopping point: inventory first, reconcile only what's confirmed.

## Phase 1 — Inventory (bounded, look-and-report, no code changes)

Catalog every UI treatment in the Argus frontend that represents "this
went wrong" to the user. For each: the component, what triggers it, its
current visual treatment (color/border/icon/copy), and whether the same
underlying situation can render through more than one code path (the exact
shape of the PR #311 bug — live vs. hydrated giving different weight to
the same event).

Known categories to check, not exhaustive — grep broadly, don't stop at
this list:

- Retryable failures (the proven pair: `assistantRecoveryCode` vs.
  `UserTurnRecovery` in `ChatMessage.tsx`).
- Non-retryable / invalid-state failures (`artifact_action_invalid_state`
  and similar stale/unauthorized-source handling).
- Backtest/job terminal states — `failed`, `canceled`, `expired` on the
  result card.
- Guest-mode limit/allowance-exhausted messaging.
- Any network/connectivity-level failure surface, if one exists.

Explicitly also confirm these are NOT drifting into failure treatment,
since the guardrail below depends on it: clarification requests and
unsupported-capability answers. These are normal conversation, not
failures — worth checking they're internally consistent with each other
too, not just correctly excluded from amber.

Output, per inventoried item: a screenshot of its current treatment (or
one per state, if the same item can render more than one way — that's the
whole point, per the PR #311 case), plus the agent's own suggestion for
how it should reconcile if inconsistent. Not a bare table — the founder is
reviewing visuals and proposals, not a list of component names.

## Phase 1 gate — HARD STOP, no exceptions

Do not proceed to Phase 2 for any reason. Post the inventory (screenshots
+ suggestions) and stop. Wait for explicit founder sign-off on which items
are genuinely "the same failure class, inconsistently treated" (in scope)
versus "intentionally different for a real reason" (out of scope, leave
alone) — that's a product judgment, not the agent's to make. This is a
literal stop condition, not a soft checkpoint to move past if nothing
seems ambiguous.

## Phase 2 — General steps once the gate clears (not a locked plan)

Exact scope depends entirely on what Phase 1 finds and what the founder
confirms — these are principles to apply to whatever's approved, not a
pre-written procedure. The one item already proven (amber/muted retry
pair) has more specific shape already worked out below; anything else
confirmed at the gate follows the same principles without a pre-written
recipe.

For the proven item, the shape already worked out:

1. **Keep the coalescing/anchoring behavior as-is.** Anchoring the failure
   to the user's turn is correct information architecture — "your request
   failed," not "the assistant said something odd." Do not revert to
   always showing the assistant-side bubble.
2. **Fix only the visual weight.** Give `UserTurnRecovery` the same
   border/background/warning-icon treatment as `assistantRecoveryCode`.
   The two forms should differ in placement, never in weight.
3. Verify across every producer: result follow-ups, composition failures,
   discovery, and retest.

For every item (proven and newly confirmed alike):

4. **Use one shared treatment definition per failure class, not hand-synced
   duplicates.** The root cause across this whole lane is the same shape:
   independently-styled implementations drifting apart with nothing
   keeping them aligned. Extract shared style/component sources so each
   bug class can't recur by construction — not just make things match
   today and leave them free to drift again next quarter.
5. **Guardrail, non-negotiable, applies lane-wide:** each failure class's
   visual weight stays strictly scoped to what actually triggers it today.
   Reconciling visual weight must never mean loosening a gate condition to
   cover a new case. Amber (or whatever a given class's treatment is)
   everywhere is amber nowhere.

## Stop and report if

- Reconciling any item would require touching underlying logic beyond
  styling (e.g. `normalizeDurableRetryActionHistory`'s coalescing) — that's
  explicitly being kept as-is for the proven item, and the same principle
  holds for any other item found.
- Matching visual weight for any item would require loosening a gate
  condition to cover a case it doesn't already cover.
- The inventory surfaces something ambiguous — a case where it's genuinely
  unclear whether two treatments should match — flag it for the founder
  gate rather than guessing.

## Where it stops

Phase 1 is a required deliverable (screenshots + suggestions, posted for
review) with a hard stop — not optional, not skippable if nothing looks
ambiguous to the agent. Reconciliation ships as one PR (or a few, if the
confirmed list is large — founder's call after seeing Phase 1) against
`codex/private-alpha-next`. Proof: screenshot evidence per reconciled
item, in both/all the states that previously diverged — visual match, not
a test count, is what actually proves each one fixed.
