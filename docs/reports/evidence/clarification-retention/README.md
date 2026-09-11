# A clarification reply keeps what the user already said

Lane branch `claude/dca-clarification-retention-1578cd`, base integration
`46d43c1d` (`origin/codex/private-alpha-next` on 2026-09-11). Fix commits
`368fe918`, `ee15a349` (Codex round 1), `a658c7ad` (Codex round 2) and
`1d41d9f4` (Codex round 3). This folder holds the reproduction on the base, the deterministic
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
asset universe on turn 2; that repair's own receipt now marks the artifact so
the merge ignores it. That replay is a committed test.

## What changed

- `src/argus/agent_runtime/stages/interpret_internal/shared.py`:
  `_turn_continues_pending_setup`. The runtime asked (the previous stage
  awaited the user) and a pending strategy exists, so the reply continues that
  setup whatever act the interpreter labeled it, with one exception: an
  explicit fresh-task read (`new_idea` and `new_task`) starts clean whatever
  the draft holds, complete or not, and what it lacks is asked for rather
  than inherited. `_pending_setup_continuation_reason_codes` records the
  override as `pending_setup_continuation_merged`.
- `interpreter/shared.py`: `repaired_turn_act`, the one owner of the act a
  repaired read carries. A known act is the model's read and stays; an act a
  repair replaces (none, `unsupported_request`) is decided by whether the
  runtime is waiting on its own question, and that assumption is recorded as
  `pending_setup_reply_assumed_without_model_read`. The focused strategy
  repair, the DCA contract audit and the seedless fallback read it; the
  prose override keeps the act it was handed.
- `contextual_merge.py`: the merge gate reads that predicate; an incoming
  asset universe that holds only the benchmark repair's artifact does not
  replace the pending asset. `asset_resolution.py`: the hidden-context guard, which clears an
  asset a new idea did not name, does not run on a continuation.
- `interpreter/dca_audits.py`: an audit may add a money role only for a
  distinct amount, and the role it names decides the field. A seed the user
  typed is never re-typed as a cap (`dca_budget_audit_outranked_by_typed_seed`);
  a budget the audit calls starting capital lands in `initial_capital` only
  while that role is empty (`dca_budget_audit_typed_as_seed`); beside an
  occupied seed it can only bound the plan, so it becomes the ceiling
  (`dca_budget_audit_seed_role_occupied_read_as_ceiling`); a distinct cap is
  still a ceiling. The role names come from `DCA_SEED_ROLES` and
  `DCA_CEILING_ROLES` in `argus/domain/dca_capital.py`.
  `_seed_corroborated_by_fidelity_audit`: a seed the primary typed without
  provenance keeps its value when the fidelity audit reads the same distinct
  starting capital beside the contribution (`stated_run_field_seed_corroborated`).
- `semantic_integrity.py`: a ceiling key whose provenance names a seed role is
  read as the seed when it is the seed's own money, a lone or an equal amount
  (`semantic_dca_seed_role_read_over_ceiling_key`); a distinct amount stays a
  ceiling. A seed key whose provenance names a ceiling role is read as the
  ceiling (`semantic_dca_ceiling_role_read_over_seed_key`). When both slots
  are crossed, each amount moves to the slot its role names and both codes
  are recorded.
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
| `tests/agent_runtime/test_pending_setup_continuation.py` (fields × families × labels × en/es-419, the fresh-task escape, the act owner's invariant table, the recorded two turns through the real workflow) | 96 passed |
| `tests/agent_runtime/test_dca_money_role_audits.py` | 31 passed |
| `tests/test_visible_reply.py` (owner + SSE and persistence contract) | 21 passed |
| `tests/evals/test_measurement_eval_followup_snapshot.py` | 2 passed |
| Hermetic `tests/agent_runtime`, `tests/evals`, `test_interpreter_prompt_freeze.py`, `test_visible_reply.py` at `506b38a7` | 2606 passed, 2 skipped |
| `tests/domain`, `tests/context`, `tests/test_alpha_api.py`, the chat stream and action contracts, OpenAPI compatibility, the DCA readout, the release docs at `506b38a7` | 1106 passed, 2 skipped |
| `tests/test_spine_guardrails.py` | 27 passed |
| `scripts/check_modularity_budget.py` | no violations |

## Measurement cases, run live on the fix (`live_cases_after.json`)

`dca_capital_semantics_clarification_reply_keeps_earlier_facts_2026_09_10`
and its Spanish twin, typed assertions only (no judge): both **passed**.
Turn 1 reached the card with DOCN, 2025-09-10 to 2026-09-09, SPY, seed
$1,000, contribution $100 monthly, fee 0.001 and slippage 0.0005 with
`explicit_user` provenance, so the harness did not need the followup. Billed
$0.068 for both. The full suite ran afterwards on the round-1 head, below.

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

## Codex round 1 (four P1 findings on `2a1be28d`, fixed in `ee15a349`)

| Finding | Fix | Test |
| --- | --- | --- |
| An explicit switch to the benchmark symbol ("Actually test $SPY instead") kept the prior asset because the continuation rule excluded benchmark symbols | Benchmark identity is no longer evidence. Only the interpreter's own receipt, `misplaced_benchmark_asset_recovered`, marks an incoming benchmark symbol as a repair artifact the pending setup ignores | `test_an_explicit_switch_to_the_benchmark_symbol_trades_that_symbol`, `test_a_benchmark_the_repair_misread_as_the_asset_does_not_replace_the_pending_asset` |
| A seed-role budget from the audit overwrote a different typed seed and lost the cap | The seed branch runs only when the seed role is empty; a different amount beside an occupied seed becomes the ceiling under `total_budget`, recorded as `dca_budget_audit_seed_role_occupied_read_as_ceiling` | `test_budget_audit_never_replaces_an_occupied_seed_with_a_different_amount`, `test_budget_audit_never_replaces_a_seed_typed_without_provenance` |
| The reader cleared a numerically distinct ceiling whose provenance said `starting_capital` | The seed-role reading applies only to the seed's own money: lone number, or equal number; a distinct number stays a ceiling | `test_semantic_reader_keeps_a_distinct_ceiling_whose_provenance_says_seed`, `test_semantic_reader_reads_a_lone_seed_role_under_a_ceiling_key_as_the_seed` |
| The seed-role set was defined twice and repeated `_DCA_SEED_KEYS` | `DCA_SEED_ROLES` and `DCA_CEILING_ROLES` live once in `argus/domain/dca_capital.py`; the reader, the audit writer and the interpreter's total-capital vocabulary derive from them | `test_seed_and_ceiling_role_names_have_one_owner`, `test_every_seed_role_is_written_and_read_as_the_seed` |

Hermetic sweeps at `ee15a349`: 2308 passed (`tests/agent_runtime`, spine guardrails) and 980 passed (chat stream contract, prompt freeze, mocked evals, alpha API, `tests/domain`). No modularity violations, prompt fingerprint untouched.

## Full live measurement at `ee15a349` (`live-measurement.json`, `baseline-comparison.json`)

The sanctioned pre-merge gate for a runtime-behavior change (tests/evals/README.md,
Test Tiers), run once on the round-1 head with a clean worktree,
`ARGUS_MARKET_DATA_PROVIDER_MODE` and `ARGUS_ASSET_PROVIDER_MODE` assigned to
`live_provider` in the process environment, the live asset catalog and the
calendar probe passing. 71 cases, 64 passed, 7 failed, no infrastructure
errors, $1.41 billed, 40 minutes. Compared case by case against the
fingerprint's baseline, `docs/reports/evidence/decision-10/live-measurement.json`
(63 passed, 6 failed at `60e7c0ec`), with `drivers/compare_baseline.py`:

| Verdict | Count | Cases |
| --- | ---: | --- |
| unchanged | 58 | 57 passing both times, plus `asset_discovery_not_result_followup_issue_244`, the known open bug (#590) |
| fixed | 5 | `asset_discovery_category_spanish_issue_244` and `asset_discovery_old_pharma_escalation_exact_issue_344` (the baseline's synthetic-market-data failures, now on live data), `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run`, `graceful_recovery_spanish_weekly_options_aapl`, `ordinary_conversation_concept_compound_interest_en` |
| added | 2 | the two recorded-repro cases, both passed |
| regressed | 6 | see below |

The six "regressed" verdicts were each rerun once, alone, with the prose judge
on (`rerun-regressed-cases.json`, $0.08): all six passed. Their first-run
failure modes were provider-side. `action_chip_add_asset_preserves_modeled_costs_issue_271`
and `dca_capital_semantics_truncated_window_measures_served_issue_455` ended in
`coverage_recovery` with `market_data_unavailable` from the market-data
preflight (MSFT/AAPL and RDDT). `dca_capital_semantics_explicit_cap_refused_by_name_issue_455`
hit a 20-second grok timeout and then a haiku response that failed schema
validation, so the seedless focused repair ran, and that path has no field for
a plan-wide cap; eight grok timeouts landed in the run overall.
`asset_discovery_peer_anchor_english_issue_244` and
`ordinary_conversation_price_question_en` were prose-judge honesty verdicts.
`action_chip_change_asset_compound_replace_issue_188` was answered as a
conversation follow-up on the first run and as the expected compound edit on
the rerun. No case failed on a typed check that this lane's code owns.

Observed, not changed: after both interpretation candidates fail, the
seedless focused-extraction repair cannot carry a plan-wide cap, so a "don't
invest more than" statement is lost on that path.

The prompt fingerprint is untouched; `tests/test_interpreter_prompt_freeze.py`
passes at this head, so the fingerprint's own `last_measured` is not moved.

## Codex round 2 (a P1 and a P2 on `b1e506ea`, fixed in `a658c7ad`)

| Finding | Fix | Test |
| --- | --- | --- |
| "New idea: DCA $200 monthly into AAPL during 2025" read as a new idea and a new task still merged with the pending AAPL setup because the symbol did not change, so the card inherited the $1,000 seed, fees and slippage | An explicit fresh-task read wins over asset equality: a new idea that names another traded asset, or that states a complete task on its own (the contract's own required-fields owner decides), starts clean. Only a partial new-idea read while the runtime awaits a reply is that reply | `test_an_explicit_fresh_task_on_the_same_asset_does_not_inherit_the_pending_setup` (en, es-419); the continuation matrix now skips complete fresh-task reads under the same owner |
| An em dash arriving as its own stream chunk was dropped with no replacement, so the live reply read "Hello world" while the saved reply read "Hello, world" | `ReplyRewrites.token` holds a chunk's trailing boundary characters (spaces, dashes) for the next chunk and rewrites a chunk that opens on a dash against the text already shown, so live and persisted text are the same | `test_streamed_chunks_render_exactly_what_the_final_reply_persists` (English and Spanish chunkings, punctuation and line-start cases) |

### The haiku path for `dca_capital_semantics_explicit_cap_refused_by_name_issue_455` (`haiku-check/`)

In the full live run this case failed after grok timed out and haiku answered
the interpretation (executable, starting capital 0.0). Its rerun passed on
grok and never exercised that path. With `ARGUS_STRUCTURED_MODEL` and
`ARGUS_STRUCTURED_FALLBACK_MODEL` set to `anthropic/claude-haiku-4.5` in the
process environment (`drivers/haiku_case.py`), three runs each:

| Tree | Attempt 1 | Attempt 2 | Attempt 3 | Cost |
| --- | --- | --- | --- | ---: |
| `origin/codex/private-alpha-next` at `46d43c1d` | passed, ceiling refused | **failed, executable, starting capital 0.0** | passed, ceiling refused | $0.076 |
| this head (`ee15a349` code) | passed, ceiling refused | passed, ceiling refused | passed, ceiling refused | $0.089 |

This PR does not change the outcome for the worse: the integration base
already loses the cap one time in three when haiku reads the interpretation,
and this head held it three times. The loss is haiku's read of the cap, not
a layer this lane owns; no code change was made for it.

### Measurement cases the round-2 fix touches, live at `a658c7ad` (`live-touched-cases-a658c7ad.json`)

The continuation rule change reaches every case where a reply arrives while a
setup is pending: the two recorded-repro cases (en, es-419), the two prebaked
chip followups (en, es-419) and `action_chip_change_asset_no_active_ref_fresh_idea_issue_188`,
the fresh idea stated during a pending clarification. All five passed with the
judge on, $0.19. The em dash change touches no measurement case; it lives in
the SSE and persistence boundary that `tests/test_visible_reply.py` covers.

## Codex round 3 (a P1 and a P2 on `51695446`, fixed in `1d41d9f4`)

| Finding | Fix | Test |
| --- | --- | --- |
| Occupied-seed detection read the aggregate total-capital vocabulary, so a cap the primary read slotted under `initial_capital` with the role `total_budget` counted as a typed seed and the audit's matching cap was outranked | A seed is the user's own only under a user or seed role (`_USER_SEED_SOURCES`); a ceiling role under the seed key is a cap in the wrong slot. The semantic reader gained the mirror rule: a seed key whose provenance names a ceiling role is read as the ceiling (`semantic_dca_ceiling_role_read_over_seed_key`) | `test_a_cap_slotted_as_the_seed_with_a_ceiling_role_is_not_a_typed_seed`, `test_semantic_reader_treats_a_seed_key_with_a_ceiling_role_as_the_ceiling`, `test_a_seed_typed_under_a_seed_or_user_role_still_outranks_the_audit` |
| A reply that ends on an em dash left the held boundary in the token carry with nothing flushing it, so the live stream read "Hello" while the persisted reply read "Hello." | `ReplyRewrites.flush()` shows what a chunk held for a next chunk that never came; the stream flushes it as a last token frame when the final event arrives | `test_a_reply_that_ends_on_a_held_boundary_is_flushed_when_the_stream_closes` (en, es-419), `test_chat_stream_flushes_a_trailing_em_dash_before_the_final_frame` |

### Measurement cases the round-3 fix touches, live at `1d41d9f4` (`live-touched-cases-1d41d9f4.json`)

The money-role change reaches every DCA case that states a seed or a cap:
`dca_capital_semantics_only_have_amount_is_ceiling_issue_455`,
`dca_capital_semantics_explicit_cap_refused_by_name_issue_455`,
`dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455`,
`dca_capital_semantics_spanish_seed_and_contribution_issue_455` and the two
recorded-repro cases (en, es-419). All six passed with the judge on, $0.13.
The stream flush touches no measurement case; the SSE contract test covers it.

## Codex round 4 (two P1s on `69be7253`, fixed in `506b38a7`)

| Finding | Fix | Test |
| --- | --- | --- |
| "New idea: DCA $200 monthly into AAPL" read as `new_idea`/`new_task` without dates still merged with the pending setup because the completeness gate called a partial fresh task a reply, so the card inherited the 2024 dates, the $1,000 seed, the fee and the slippage | The completeness gate is gone: a `new_idea`/`new_task` read starts clean whatever the draft holds, and what it lacks is asked for. The same class swept: the focused strategy repair, the DCA contract audit and the seedless fallback each relabeled the act on their own; the act now has one owner, `interpreter/shared.repaired_turn_act` (a known act is the model's read and stays; an act a repair replaces is decided by the runtime's own pending question and recorded as `pending_setup_reply_assumed_without_model_read`) | `test_a_partial_fresh_task_read_stays_fresh_and_asks_for_what_it_lacks` (en, es-419), `test_a_repair_keeps_a_known_act_and_decides_a_replaced_one_from_the_pending_state` |
| `initial_capital=5000` under the role `total_budget` beside `total_capital=1000` under the role `starting_capital` lost the $5,000: the first branch cleared it because a distinct number already sat in the ceiling slot, then the mirror rule moved $1,000 to the seed and left no ceiling | The reader looks at both slots before moving anything; when both are crossed each amount moves to the slot its role names (seed 1000, ceiling 5000) and both codes are recorded | `test_semantic_reader_swaps_crossed_money_roles_and_keeps_both_amounts` |

### Measurement cases the round-4 fix touches, live at `506b38a7` (`live-touched-cases-506b38a7.json`)

The fresh-task rule and the act owner reach every case that answers a pending
setup or opens a fresh idea beside one: the two recorded-repro cases (en,
es-419), the two prebaked-chip followups, and
`action_chip_change_asset_no_active_ref_fresh_idea_issue_188`. The money-role
change reaches the four DCA seed-or-cap cases again. All nine passed with the
judge on, $0.32.

## Billed cost

| Item | Cost |
| --- | ---: |
| Three live reproduction runs on the base | $0.173 |
| Base backend during the browser demo, including two aborted driver attempts | $0.246 |
| Fixed backend during the browser demo | $0.112 |
| Two measurement cases live | $0.068 |
| Full live measurement at `ee15a349` | $1.412 |
| Six regressed cases rerun with the judge | $0.081 |
| Haiku check of the cap case, three runs on the base and three on this head | $0.165 |
| Five touched measurement cases live at `a658c7ad` | $0.187 |
| Six touched measurement cases live at `1d41d9f4` | $0.130 |
| Nine touched measurement cases live at `506b38a7` | $0.321 |
| **Total** | **$2.90** |

## Observed, not changed here

- The turn-2 restatement on a ready card is answered with "No requested
  changes were applied. Please restate what you want to change." (en) or
  "La confirmación visible sigue lista." (es-419). Both are truthful and keep
  the card; neither re-asks a fact.
- The persisted content of that Spanish reply is the English recovery text
  while the UI renders the localized copy from typed metadata.
