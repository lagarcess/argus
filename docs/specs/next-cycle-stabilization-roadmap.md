# Next-Cycle Stabilization Roadmap (DRAFT — founder ranks final)

Locks in every open issue and open PR as of 2026-08-05, the day after the
production promotion. Ranking is proposed by impact and dependency order;
the founder's triage decides the final order. Companion board:
[`next-cycle-product-roadmap.md`](next-cycle-product-roadmap.md).

## Tier 1 — production-degrading, user-facing (from live alpha feedback)

1. **Interpreter ValueError dead end** (to file at triage — top candidate).
   Both interpretation tiers fail with `error_type=ValueError` on certain
   input shapes (knowledge questions, bare period replies); the user gets the
   `interpreter_unavailable` banner and Reintentar loops forever because the
   failure is deterministic. Production evidence 2026-08-05 03:45:07 and
   03:48:06. First step: log the ValueError detail (only the type is logged
   today), then remove the validator rejection. Degrades every intent it
   touches and manifests as the banned dead end.
2. **Conversation edit contract cluster** — #335 (inline card editing) under
   the #141 macro, with the #237 program as umbrella. Four live faces from
   2026-08-05 feedback: pending-card NL edits ignored (any language),
   compound post-result edits unrouted ("el año 2023, y agrégale a NVDA"),
   clarify-loop answers failing ("del ultimo año para aca"), and Argus's own
   suggestion chips dead-ending (see item 3). Founder contract: every
   parameter on a confirmation card must resolve gracefully inside the card.
3. **Knowledge-suggestion prebake gap** (to file at triage). General-knowledge
   suggestion rows ("Simular AVGO") submit bare label text with no runnable
   config attached; the interpreter slots the label as a strategy name and
   refuses. Grounded discovery already solved this by prebaking only
   confidently-runnable suggestions — copy that pattern.
4. **Knowledge/statistics intent answering** (to file at triage). "Ayúdame
   con estadísticas sobre el S&P 500" must get a knowledge answer, not a
   confirmation-card interrogation ("¿Qué periodo quieres usar?") or an
   unsupported-strategy refusal. Related macro (founder thinking): index
   names vs tradable proxies (S&P 500 → SPY).
5. **#378 reply language** — responses follow workspace language, not message
   language; plus any remaining unlocalized templates (the deterministic
   English block was retired at `72d2fe3a`).

## Tier 2 — harness and operations

6. **#383 canary automation** (session-injected journey, API-layer denial
   probe, staging testing sitekey; includes the probe-labeling and
   retry-once fixes). Restores the daily alarm; until it ships the scheduled
   canary stays red at browser auth by design.
7. **#376 durable idempotency for guest funnel events.**
8. **#367 focused repair drops explicit modeled costs.**
9. **OpenRouter three-key routing lane** (to file at triage): route
   argus-guest / argus-prod / argus-dev keys in code per the documented
   policy; today code reads only `OPENROUTER_API_KEY`.

## Tier 3 — design locks, polish, and debt

10. **PR #363 (open) + #333 + parked #363 design**: the current-data window
    semantics need the founder's design lock (clamp-to-earliest,
    disposition-aware Retest, guided repair, reconciliation — context
    recorded in the roadmap). The open PR waits on that lock.
11. **#332 fractional-period rounding.**
12. **#314 rejected-action operational evidence.**
13. **#350 display-font fallback stack.**
14. **#236 chat-turn service extraction** (plus standing modularity debt:
    `llm_interpreter.py` at budget ceiling).
15. **Evals**: #369 (retain judged prose), #365 (composer outage scoring),
    #364 (comparison relationship flips).
16. **Floor-banner copy**: `interpreter_unavailable` recovery must own the
    failure and offer a step (secondary to item 1, which removes most
    occurrences).
17. **Dead-code strips** (chips queued): Strategies + Collections surfaces;
    `ARGUS_ASSET_PROVIDER_MODE` alias.
18. **`scripts/qa/write-local-env.sh`** must stop overwriting canonical env
    files (acceptance-rule follow-through).

## Waiting on data or founder decision

- **#294 guest allowance tuning** — waits on the funnel window now flowing.
- **#244 discovery exposure** — discovery is live; founder decides close vs
  remaining exposure scope.
- **#379 run-action token chip** — closed pending founder design discussion
  (localized chip, no message metering, typed equivalent).

## Open PRs on the board

- **#384 (draft)** — founder's try-next peer-discovery research capsule (the
  smarter recommender line of work).
- **#363** — retest window truthfulness; blocked on the design lock above.
- **#307 (draft)** — personalization persistence checkpoint (incubation lane;
  see the product roadmap).
