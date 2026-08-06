# Next-Cycle Stabilization Roadmap

Opened 2026-08-05, the day after the production promotion. Founder-ranked
2026-08-06. Companion board:
[`next-cycle-product-roadmap.md`](next-cycle-product-roadmap.md).

## Ranking criteria (founder-locked 2026-08-06)

1. **User-visible production harm outranks everything.** A live dead end beats
   any amount of internal debt.
2. **Non-overlapping file ownership.** Lanes run in parallel worktrees only when
   they do not touch the same files. Where two lanes share a spine file, they
   serialize.
3. **Freeze parallelization when a lane needs a clean landing zone.** A lane
   that must reconcile against a moving base gets the base held still.
4. **Whole lanes, not chunks.** A lane is dispatched to completion, including
   its tests, evidence, and docs, not sliced into review checkpoints unless the
   lane is incubation by design.
5. **Nothing merges on self-report.** Per-lane founder gate, exact-head
   evidence, browser proof for anything user-facing.

## In flight

- **PR #363 — Retest current-data windows.** Founder-locked redesign shipped:
  the waste guard moved out of the chat turn into the dossier button, computed
  server-side before any click. Same-period Retest now spends nothing. Two
  repairable provider windows offer one exact clamp-start repair; unsupported
  timeframe stays an honest dead end. Evidence captured in both languages.
  Reconciling onto the post-#385 integration tip. Closes #333.
- **PR #386 — Personalization memory.** See the product board; it carries the
  #307 persistence tranche inside it, so #307's alignment question governs both.
- **Interpreter ValueError lane.** Complete and locally verified, not yet
  pushed. See Tier 1 item 1.

## Tier 1 — production-degrading, user-facing

1. **Interpreter ValueError dead end** — work complete, awaiting founder
   review and PR. Root cause confirmed from production `route_receipts`: both
   tiers returned valid responses and a local post-response validator rejected
   them, so the failure was deterministic and the retry could never succeed.
   Of the three rejection sites, one was a false positive discarding a good
   knowledge answer and is now fixed; the two genuine ones get one bounded
   in-tier self-correction before falling through, and no longer render a
   retryable dead end. Rejections are now observable in telemetry without
   breaking the calibrated corridor contract. Extracted
   `interpreter/contract_recovery.py` to stay inside the modularity budget.
2. **Conversation edit contract cluster** — #335 (inline card editing) under the
   #141 macro, with #237 as umbrella. Four live faces from 2026-08-05 feedback:
   pending-card NL edits ignored in any language, compound post-result edits
   unrouted, clarify-loop answers failing, and Argus's own suggestion chips
   dead-ending. Founder contract: every parameter on a confirmation card must
   resolve gracefully inside the card.
3. **Knowledge-suggestion prebake gap** (to file). General-knowledge suggestion
   rows submit bare label text with no runnable config, so the interpreter slots
   the label as a strategy name and refuses. Grounded discovery already solved
   this by prebaking only confidently-runnable suggestions.
4. **Knowledge/statistics intent answering** (to file). A statistics question
   must get a knowledge answer, not a confirmation-card interrogation or an
   unsupported-strategy refusal. Related macro: index names versus tradable
   proxies. **Note:** the Tier 1 item 1 fix changed this item's symptom. The
   dead-end banner is gone; the same input now surfaces the model's refusal.
   Reproduce against current behavior, not the old banner.
5. **#378 reply language** — responses follow workspace language, not message
   language, plus any remaining unlocalized templates.

## Tier 2 — harness and operations

6. **#383 canary automation — partially shipped in #385 (merged 2026-08-06).**
   Landed: the API-layer denial probe with its own labeled failure and
   retry-once, and deployed-SHA evidence binding. Also fixed en route: the
   scheduled canary had been checking out the integration branch while
   validating production, so it failed at the deploy gate every day and never
   reached the checks it existed to run. Two review findings were caught and
   fixed before merge, a signup enumeration oracle and a false-evidence path
   where ancestry matching let the artifact name a commit that was never
   deployed. **Still open:** session injection for the browser golden path
   (#383 item 2) and login-form coverage on a staging sitekey (item 3). The
   canary stays red until the merged API change is deployed; that is expected,
   not a defect.
7. **#376** durable idempotency for guest funnel events.
8. **#367** focused repair drops explicit modeled costs.
9. **OpenRouter three-key routing lane** (to file): route argus-guest /
   argus-prod / argus-dev keys in code per the documented policy; today code
   reads only `OPENROUTER_API_KEY`. Blocks product-board dev-cost accounting.

## Tier 3 — design locks, polish, and debt

10. **#332** fractional-period rounding.
11. **#314** rejected-action operational evidence.
12. **#350** display-font fallback stack.
13. **#236** chat-turn service extraction, plus standing modularity debt.
    `llm_interpreter.py` and `stages/interpret.py` both sat one line under
    budget before the interpreter lane and required extraction to change at
    all; the next person to touch them hits the same wall immediately.
14. **Evals**: #369 (retain judged prose), #365 (composer outage scoring),
    #364 (comparison relationship flips).
15. **Floor-banner copy** — `interpreter_unavailable` recovery must own the
    failure and offer a step. Largely absorbed by Tier 1 item 1, which removed
    most occurrences and the non-retryable dead end.
16. **Dead-code strips**: Strategies and Collections surfaces;
    `ARGUS_ASSET_PROVIDER_MODE` alias.
17. **`scripts/qa/write-local-env.sh`** must stop overwriting canonical env
    files.
18. **Auth denial audit events** (new, from #385 review). Argus emits nothing
    when an auth attempt is denied, so there is no audit trail for a gated
    private alpha. Deferred deliberately as premature infrastructure; revisit
    before public exposure.

## Waiting on data or founder decision

- **#294** guest allowance tuning — waits on the funnel window.
- **#244** discovery exposure — founder decides close versus remaining scope.
- **#377** Perplexity finance/web search modes as a discovery provider upgrade.
- **#379** run-action token chip — closed pending founder design discussion.
