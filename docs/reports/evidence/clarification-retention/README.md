# A clarification reply keeps what the user already said

Lane branch `claude/dca-clarification-retention-1578cd`, base integration
`46d43c1d` (`origin/codex/private-alpha-next` on 2026-09-11). Fix commit
`368fe918`. This folder holds the reproduction on the base, the deterministic
replay of the recorded provider reads before and after, the live browser demo
in English and Spanish before and after, the two new measurement cases run
live, the engine check of the start-day contribution, and every billed cost.

## The recorded turns (2026-09-10, English workspace)

1. "Test monthly dollar-cost averaging in DOCN from September 10, 2025 through
   September 9, 2026. Start with $1,000 of starting capital, then contribute
   $100 every month. The $1,000 is starting capital, not a total contribution
   cap. Compare with SPY. Model a 10 basis point fee and 5 basis points
   slippage per trade." Argus asked which direction to go because it could
   not treat the $1,000 as both starting capital and a cap.
2. "Use $1,000 as starting capital only. There is no contribution cap. Add
   $100 monthly after the initial investment. Keep the dates, SPY benchmark,
   10 bps fee and 5 bps slippage." Argus replied "Got it — ..." and asked for
   the asset and the date window again.

## Reproduction on the base (`46d43c1d`)

### Live, three runs of the two turns in-process (`live/before_en*.json`)

The runtime, the interpreter and every audit ran against the live models and
the live asset catalog (`drivers` in the scratch folder; provider payloads are
stripped of the prompt text). The recorded reads did not come back on demand:

| Run | Turn 1 | Turn 2 | Cost |
| --- | --- | --- | ---: |
| 1 | Card, **starting capital $0** (the seed was dropped: the primary read typed `initial_capital: 1000` with no provenance map and the projection discarded it) | Card, $1,000 after the restatement was applied as an edit | $0.069 |
| 2 | Card, $1,000 | "The visible confirmation is still ready." | $0.053 |
| 3 | Card, **starting capital $0** (same loss) | Card, $1,000 | $0.052 |

The recorded clarification about a cap did not appear in three runs; the
same head dropped the $1,000 seed in two of them. Both losses are the same
class: a deterministic layer deciding a money role on its own.

### Deterministic replay of the recorded reads (`replay/`)

`replay_<variant>.json` runs the real LangGraph runtime (memory checkpointer,
live asset catalog, no model cost) with every structured provider call
answered by the recorded shapes: the primary read with the seed typed
explicitly, `DcaContributionRoleAudit` = `recurring_contribution_explicit:
true, total_budget_not_recurring: true`, and on turn 2 a transport error on
the primary, a fallback read without asset or dates, `FocusedStrategyExtraction`
with `date_range: null` and `FocusedDateWindowExtraction` with
`has_date_window: false`. The variant is what `DcaContractAudit` said about
the $1,000.

| `DcaContractAudit` budget read | Turn 1 before | Turn 2 before | Turn 1 after | Turn 2 after |
| --- | --- | --- | --- | --- |
| none | card | **re-asks asset and dates**, reply shows the em dash | card, seed $1,000 | card, seed $1,000 |
| $1,000 as `starting_capital` | **cap clarification** (`unsupported_dca_contribution_ceiling`) | re-asks asset and dates | card, seed $1,000 | card, seed $1,000 |
| $1,000 as `cap` | cap clarification | re-asks asset and dates | card, seed $1,000 | card, seed $1,000 |
| $1,000 as `total_budget` | cap clarification | re-asks asset and dates | card, seed $1,000 | card, seed $1,000 |

Turn 1 before: any budget read, even one the audit itself labels
"starting_capital", was written under the `total_budget` key beside the
explicit `initial_capital`, and the semantic reader refused the plan as
capped. Turn 2 before: the merge that carries the pending setup only fired
when the model labeled the turn a continuation or a `requested_field` was
set, and an unsupported-recovery question sets neither, so the facts were
lost even in the variant whose turn 1 had reached a card.
`replay_hermetic.json` is the same replay with the synthetic fixture (AAPL),
where the interpreter's benchmark-misplacement repair also put SPY into the
asset universe on turn 2; the merge now treats an incoming asset that is only
a benchmark mention as a repair artifact. That replay is a committed test.

## What changed

- `src/argus/agent_runtime/stages/interpret_internal/shared.py`:
  `_turn_continues_pending_setup`. The runtime asked (the previous stage
  awaited the user) and a pending strategy exists, so the reply continues that
  setup whatever act the interpreter labeled it. Only a reply that itself
  names another traded asset (a cashtag, an uppercase ticker, a user mention
  or explicit provenance; never a benchmark mention) starts a new idea.
  `_pending_setup_continuation_reason_codes` records the override as
  `pending_setup_continuation_merged`.
- `contextual_merge.py`: the merge gate reads that predicate; an incoming
  asset universe that is only benchmark symbols does not replace the pending
  asset. `asset_resolution.py`: the hidden-context guard, which clears an
  asset a new idea did not name, does not run on a continuation.
- `interpreter/dca_audits.py`: an audit may add a money role only for a
  distinct amount, and the role it names decides the field. A seed the user
  typed is never re-typed as a cap (`dca_budget_audit_outranked_by_typed_seed`);
  a budget the audit calls starting capital lands in `initial_capital`
  (`dca_budget_audit_typed_as_seed`); a distinct cap is still a ceiling.
  `_seed_corroborated_by_fidelity_audit`: a seed the primary typed without
  provenance keeps its value when the fidelity audit reads the same distinct
  starting capital beside the contribution (`stated_run_field_seed_corroborated`).
- `semantic_integrity.py`: a ceiling key whose provenance names a seed role is
  read as the seed (`semantic_dca_seed_role_read_over_ceiling_key`).
- `src/argus/api/chat/visible_reply.py`: the one owner of the em dash rule at
  the point a reply becomes visible. Token frames, the final payload text and
  the persisted message pass through it; the turn records `reply_rewrites`
  (`docs/API_CONTRACT.md`).
- `tests/evals/measurement_eval_harness.py`: a followup turn runs against the
  setup the first turn built (the workflow's own snapshot builder), not
  against an absent snapshot.
- No model-facing text changed; `tests/test_interpreter_prompt_freeze.py`
  passes and the fingerprint is untouched.

## Tests

| Suite | Result |
| --- | ---: |
| `tests/agent_runtime/test_pending_setup_continuation.py` (fields × families × labels × en/es-419, the new-idea escape, the recorded two turns through the real workflow) | 85 passed |
| `tests/agent_runtime/test_dca_money_role_audits.py` | 13 passed |
| `tests/test_visible_reply.py` (owner + SSE and persistence contract) | 11 passed |
| `tests/evals/test_measurement_eval_followup_snapshot.py` | 2 passed |
| Hermetic `tests/agent_runtime` + `tests/test_spine_guardrails.py` | 2294 passed |
| `tests/test_chat_stream_contract.py`, `test_interpreter_prompt_freeze.py`, the mocked eval suites, `tests/test_alpha_api.py` | 408 passed |
| `scripts/check_modularity_budget.py` | no violations |

## Measurement cases, run live on the fix (`live_cases_after.json`)

`dca_capital_semantics_clarification_reply_keeps_earlier_facts_2026_09_10`
and its Spanish twin, typed assertions only (no judge): both **passed**.
Turn 1 reached the card with DOCN, 2025-09-10 to 2026-09-09, SPY, seed
$1,000, contribution $100 monthly, fee 0.001 and slippage 0.0005 with
`explicit_user` provenance, so the harness did not need the followup. Billed
$0.068 for both. The full live measurement suite was not run in this lane.

## Browser demo (`browser/`)

Real chat UI at `localhost:3000` under mock auth, backend on `:8000` with live
market data, live models. "Before" is the base tree served from a detached
worktree at `46d43c1d`; "after" is the lane head. The Spanish runs switched
the profile language to `es-419` first.

| Run | Turn 1 | Turn 2 | Screenshots | Cost |
| --- | --- | --- | --- | ---: |
| before, en | Card with **Starting capital $0** | Card with $1,000 (restatement applied as an edit) | `before-en-turn1.png`, `before-en-turn2.png` | $0.055 |
| before, es-419 | Card, capital inicial $1,000 | Card, $1,000 | `before-es-419-turn1.png`, `before-es-419-turn2.png` | $0.078 |
| after, en | Card, starting capital $1,000 | Card unchanged, $1,000; the runtime says no changes were applied | `after-en-turn1.png`, `after-en-turn2.png` | $0.069 |
| after, es-419 | Card, capital inicial $1,000 | "La confirmación visible sigue lista." | `after-es-419-turn1.png`, `after-es-419-turn2.png` | $0.043 |

No em dash was shown in any of the eight turns; the models did not write one
this time, so `reply_rewrites` never fired in the demo. Its behavior is
covered by `tests/test_visible_reply.py`. The base run reproduced the seed
loss in the browser (English) and not the cap clarification, consistent with
the in-process runs above.

## The start-day $100 (`engine/docn-dca-flows.txt`)

The engine was run directly on live DOCN bars for the recorded plan ($1,000
seed, $100 monthly, 10 bps fee, 5 bps slippage). The stored external flows
put **$1,100 on 2025-09-10**: the seed plus a $100 contribution on the first
bar, then $100 on the first trading day of each month through 2026-09-01.
That is 13 entries and $2,300 invested, exactly the recorded run. This is
engine semantics in `_dca_equity_curve` and `signals.py` (an entry lands on
the first bar of every window, including the window the run opens in), not
an interpretation defect. The user said the $100 starts after the initial
investment; the engine does not distinguish that. Not changed in this lane.

## Billed cost

| Item | Cost |
| --- | ---: |
| Three live reproduction runs on the base | $0.173 |
| Base backend during the browser demo, including two aborted driver attempts | $0.246 |
| Fixed backend during the browser demo | $0.112 |
| Two measurement cases live | $0.068 |
| **Total** | **$0.60** |

## Observed, not changed here

- The turn-2 restatement on a ready card is answered with "No requested
  changes were applied. Please restate what you want to change." (en) or
  "La confirmación visible sigue lista." (es-419). Both are truthful and keep
  the card; neither re-asks a fact.
- The persisted content of that Spanish reply is the English recovery text
  while the UI renders the localized copy from typed metadata.
