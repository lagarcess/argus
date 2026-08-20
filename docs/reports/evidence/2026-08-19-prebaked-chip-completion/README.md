# Prebaked chip completion, 2026-08-19

Lane: every front-page chip (`chat.example_queries` q1/q2/q3) must reach a
complete result end to end, both languages, for any reasonable follow-up
answer. This report holds the production verification runs (before), the
root causes, the fixes on this branch, and the local at-head verification
(after).

Production under test: `arguschat.ai` at main `31343882` (the 2026-08-16
promotion, which already includes #517 and #507). Driver: the canary-pattern
service-role session for the canonical automated-QA identity, headless
Playwright journeys clicking the real chips and answering follow-ups the way
the production users did. Journey evidence (per-turn user-visible text,
screenshots, and the conversation's typed message metadata) was captured per
run; conversation ids are listed below and remain inspectable on the QA
account.

## Before: production completion rates (2026-08-19, 21:20–23:10 UTC)

A run counts as complete only when the user reaches the chip's real result
(a grounded answer for q1/q2, a finished backtest card for q3).

| Chip | EN | ES | Failure the user saw |
|---|---|---|---|
| q1 Netflix | **0/3** | **1/3** | "I couldn't complete the data lookup just now…" / "No pude completar la búsqueda de datos…" |
| q2 Costco comparison | **3/3** server-side¹ | **3/3** server-side¹ | ¹each language's background-job run rendered "Research ready — The full answer is below." / "La respuesta completa está abajo." **above nothing** until reload; the other two runs were inline cache hits |
| q3 Coca-Cola DCA | **2/3** | **1/3** | "200$", "13,000 pesos", and "un millón de pesos" all died in "I could not resolve that choice without changing your current idea." |
| typed "Ko vs pepsi" | **1/1** (with "last 3 years") | — | asks the period, then completes a KO-vs-PEP benchmark run |

q3 detail (the amount personas):

| Answer to "How much…?" | EN | ES |
|---|---|---|
| "$200 monthly" | ✅ result card | — |
| bare "500" | ✅ result card | ✅ result card (all-Spanish flow) |
| "200$" | ❌ no-progress dead end | — |
| "13,000 pesos" | — | ❌ no-progress dead end |
| "un millón de pesos" | — | ❌ no-progress dead end |

Journey → conversation id: probe-en-netflix-1 `5dc3a176`, en-netflix-2
`89c3076b`, en-netflix-3 `5d485cb2`, es-netflix-1..3 `a1277412` `d5383933`
`769b1e94`, en-costco-1..3 `fd8ddf9f` `1ced054d` `214dcc7b`, en-ko-a..c
`b386e9bc` `7f210e3e` `c779723a`, es-ko-a..c `ce953636` `48729e91`
`0996b69c`, en-kovspepsi(+2) `b29cecab` `13c760fc`, es-costco-1..3
`550323e6` `14f5972f` `8f7c0ca3` (run 1's answer, 3,387 chars, present
server-side while the view stayed empty).

The production 2026-08-11..13 user data (Netflix 2 clicks 0 completed,
Costco 1 click 0 completed, Coca-Cola 6 clicks 3 deaths) is consistent with
every failure class reproduced here, so #517/#507 did NOT close these: #517
fixed the asset-discarded re-ask (KO stayed carried in every run here) and
#507 held on language (every deterministic sentence rendered in the
workspace language), but the completion path itself still died.

## Root causes (each proven, not inferred)

1. **Every grounded research read that fetched a URL failed closed.**
   `TOOL_RATE_TABLE_USD_PER_INVOCATION` pinned `fetch_url` at $0.00025;
   Perplexity bills $0.0005 (verified against a live response and
   docs.perplexity.ai). The fail-closed cost validation rejected the whole
   response (`research_unavailable_malformed_response`, stamped in the
   message metadata of every failed Netflix run), so q1/q2 completion
   depended on whether the agent happened to use `fetch_url` — matching the
   "flips by serving day" history. The only log line was a WARNING with the
   reason in dropped structured extras.

2. **A bare amount answering "How much should I use?" was killed by three
   composed seams** (production trace 21:39–21:40 UTC + instrumented local
   replays, `repro-v2-run*.json`):
   - the `DcaContributionRoleAudit` verdict re-roled the amount into
     `total_capital` even when the primary read typed it
     `capital_amount`/`recurring_contribution` — the seed-present branch of
     #517's rule protected typed contributions, the seedless branch did not;
   - the replay detector's `material_fields` omitted every money role except
     `capital_amount`, so the audited draft (and even a
     `recurring_contribution: 200, explicit_user` repair draft) was judged a
     replay of the pending strategy and the candidate was killed
     (`InterpretationContractError`, llm_interpreter.py:2651);
   - the per-turn call allowance (7) was spent by the audits, so
     self-correction was skipped (`remaining_calls=0` in the production log)
     and the last-resort focused repair's calls were permit-denied — the
     turn collapsed into the no-progress fallback.

3. **The Costco background-job answer never rendered in the active view.**
   Durable completion only invalidated caches; the research answer is a new
   assistant message, so the open chat showed "The full answer is below."
   above nothing (full-page screenshot in the journey evidence; the answer
   message existed server-side).

4. **An empty final frame rendered nothing at all** — the "no assistant
   reply" death from the production data. The final handler's branch chain
   (confirmation → run → job → text) had no else.

5. **Two DCA ceiling-recovery options rendered English inside Spanish**
   ("Run recurring buys only", "Use it as starting capital") — no typed
   `simplification_option_kind`, so the compatibility labels leaked.

## Fixes on this branch

- `72ddbd0f` fix(research): live fetch_url rate; warnings carry
  reason+detail in the message; the job poller fails fast on deterministic
  reasons instead of burning the 600 s deadline.
- `51e7c12c` fix(interpreter): money roles are material updates (replay);
  the seedless typed-contribution rule, gated on the turn answering the
  runtime's own sizing question (receipt
  `dca_contribution_provenance_kept_over_budget_audit`); a reserved
  last-resort repair call (mirrors the routing reservation).
- `2c3ccc3d` fix(chat): a completed research job reloads the active
  transcript so its answer message appears.
- `2bc5b26b` fix(chat): typed kinds + both-bundle labels for the two
  ceiling-recovery options.
- `5d3f39b8` fix(chat): an empty final frame renders the localized
  turn-failure copy instead of silence.

## Guards (fail when a chip's completion path drops a carried fact)

- `tests/agent_runtime/test_chip_completion_guards.py` — money-role answers
  are never replays (parameterized over all four roles, plus the exact
  production budget-audited shape); the sizing-question gate on the budget
  audit (both directions: survives with the question, still demotes
  without); the reserved repair slot (both directions).
- `tests/evals/measurement_cases/dca_capital_semantics.yaml` — two-turn
  chip-shaped cases: the q3 chip text then "200$" (en) and the Spanish chip
  text then "13,000 pesos" (es-419), asserting KO + the amount + monthly all
  survive to `ready_for_confirmation`.
- `web/__tests__/chat-final-message.test.ts` — an empty final frame must
  yield a visible assistant turn.
- `web/__tests__/chat-backtest-jobs.test.ts` — research completion reloads
  the active transcript.

## After: verification at this head (live LLM + live Perplexity, local spine)

- Netflix chip first turn: grounded answer with 5 public sources, no
  degraded code — EN and ES (`ready_to_respond`,
  `research_answer_balanced_lookup`).
- Perplexity cost validation: live `run_research` SUCCESS, cost $0.2643
  validated (2 finance / 2 web / 1 fetch invocations).
- "200$" after the q3 chip: **5/5** runs reach `ready_for_confirmation` with
  `capital_amount=200`, KO/monthly/5y intact, zero replay kills (pre-fix:
  flaky locally, dead in production).
- Both new chip eval cases pass live ("200$" en, "13,000 pesos" es-419);
  "un millón de pesos" reaches `ready_for_confirmation` with
  `capital_amount=1,000,000`.
- Suites: backend `tests/agent_runtime tests/research tests/evals` 2279
  passed; web 1508/1508; modularity budget clean.

The frontend fixes (3, 4) and the deployed-pricing fix (1) can only be
production-verified after this branch deploys; re-run the six-chip journey
matrix then.

## Known residuals (out of this lane's diff)

- The runtime measurement event emission fails on every production turn
  (`argus.api.chat.measurement_events:_run:35`) — flagged as its own task.
- Provider price drift has no in-repo guard by construction; only a live
  canary probe of one cheap grounded read would catch the next drift before
  users do.
- `_incomplete_asset_context_update` (provider_context_assets.py) still
  unconditionally re-adds `asset_universe` to `missing_required_fields`; not
  implicated in any of this lane's production traces (#483's upstream fix
  held: KO was carried in every run), left untouched.

## Review round, 2026-08-20 (reconciled onto integration `e99af9a1`)

Ten findings at `57d66d24`, all confirmed and fixed; dispositions live on
the PR threads. Re-verification at the reconciled head, local stack with
live providers (every prior browser result predated these fixes):

- Cancel path (the round's regression): idea → card → Cancel settles to
  "Draft canceled" / "Borrador cancelado" with zero turn-failure fallback
  strings in either language, twice (before and after the modularity
  extraction).
- All six chip variants complete end to end in the browser: EN and ES
  Netflix (grounded revenue answers), EN and ES Costco (inline comparison
  with live market snapshot), EN KO with "200$" (card → run →
  "Simulation Complete, $17,161, +40.7% return on contributions"), ES KO
  with "13,000 pesos" (card → run → "Simulación completa, $1,115,485,
  +40.7% retorno sobre aportes").
- Both chip eval cases re-run live and pass with the re-pointed snapshots
  (`pending_needs` removed everywhere; the shipping signal is
  `requested_field` beside the `await_user_reply` outcome that set it).
- PR #522 demonstrated by execution at this head: the refusal override
  returns None for all twelve `question_kind` values with the research
  allowance exhausted (route-kept receipt noted each time); the tradability
  owner returns its three verdicts, an outage is never cached and re-probes
  after healing, a decided negative stays cached; live PENGU and WLD resolve
  but carry `no_history` and `verified_peers` offers neither; five live
  draws of `graceful_recovery_weekly_options_aapl` all land `unsupported`
  with typed recovery, zero fabricated readouts.
- Suites: backend 2732 passed, web 1508 passed, modularity budget clean
  (ChatInterface reduced back to its 2598 baseline by extracting the
  fallback composition into chat-message-projection).

Decision recorded (poller): no `ResearchUnavailableError` reason is treated
as deterministic from one poll; the deadline alone owns giving up, so a
future provider rate drift costs one 600 s deadline per job rather than
taking the rail dark instantly, and the failure posts its note.
